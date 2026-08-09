#!/usr/bin/env python3
"""Durable single-worker queue for audio-only ancient recitation scenes."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ancient_audio_templates import get_bgm_preset, get_recitation_template, get_room_preset
from audio_scene_mixer import atomic_json, render_audio_scene, utc_now


SAFE_NAME = re.compile(r"[^a-zA-Z0-9_.-]+")
ALLOWED_BGM_MIME = {
    "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a", "audio/aac": ".aac", "audio/ogg": ".ogg",
}


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def scene_summary(record: dict[str, Any]) -> dict[str, Any]:
    result = record.get("result") if isinstance(record.get("result"), dict) else {}
    return {
        "id": record.get("id"),
        "title": record.get("title"),
        "status": record.get("status"),
        "stage": record.get("stage"),
        "progress": record.get("progress", 0.0),
        "error": record.get("error"),
        "createdAt": record.get("createdAt"),
        "updatedAt": record.get("updatedAt"),
        "seedId": record.get("request", {}).get("seedId"),
        "seedName": result.get("seedName") or record.get("request", {}).get("seedName"),
        "templateId": record.get("request", {}).get("recitationTemplateId"),
        "templateName": result.get("recitation", {}).get("templateName"),
        "bgmName": result.get("backgroundMusic", {}).get("name"),
        "roomPresetId": result.get("mix", {}).get("roomPresetId") or record.get("request", {}).get("roomPresetId"),
        "durationSeconds": result.get("outputs", {}).get("wav", {}).get("durationSeconds"),
        "qualityControl": result.get("qualityControl"),
        "wavUrl": f"/audio_scenes/{record.get('id')}/master.wav" if record.get("status") == "completed" else None,
        "mp3Url": f"/audio_scenes/{record.get('id')}/master.mp3" if record.get("status") == "completed" else None,
        "dryVoiceUrl": f"/audio_scenes/{record.get('id')}/dry_voice.wav" if record.get("status") == "completed" else None,
        "manifestUrl": f"/audio_scenes/{record.get('id')}/scene.json" if record.get("status") == "completed" else None,
        "text": record.get("request", {}).get("text", ""),
    }


class AudioSceneQueue:
    """Generate locked speech and master it with BGM without blocking the UI."""

    def __init__(
        self,
        outputs: Path,
        voice_worker: Callable[[dict[str, Any]], tuple[Path, dict[str, Any]]],
    ) -> None:
        self.outputs = outputs
        self.root = outputs / "audio_scenes"
        self.root.mkdir(parents=True, exist_ok=True)
        self.voice_worker = voice_worker
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="audio-scene")
        self._recover_interrupted()

    def _record_path(self, scene_id: str) -> Path:
        safe = SAFE_NAME.sub("", str(scene_id))[:100]
        path = self.root / safe / "job.json"
        record = load_json(path, None)
        if not isinstance(record, dict) or record.get("id") != scene_id:
            raise ValueError("找不到指定聲音場景")
        return path

    def _recover_interrupted(self) -> None:
        for path in self.root.glob("*/job.json"):
            record = load_json(path, None)
            if not isinstance(record, dict) or record.get("status") not in {"queued", "running"}:
                continue
            record.update({
                "status": "interrupted", "stage": "等待手動重試", "progress": 0.0,
                "error": "工作站曾停止；為避免自動消耗 API，請手動重試。", "updatedAt": utc_now(),
            })
            atomic_json(path, record)

    @staticmethod
    def _validate(payload: dict[str, Any]) -> dict[str, Any]:
        seed_id = str(payload.get("seedId", "")).strip()
        text = str(payload.get("text", "")).strip()
        template_id = str(payload.get("recitationTemplateId", "")).strip()
        bgm_id = str(payload.get("bgmPresetId", "mountain-qin")).strip()
        room_id = str(payload.get("roomPresetId", "warm-study")).strip()
        if not seed_id:
            raise ValueError("請選擇聲音種子")
        if not text:
            raise ValueError("請輸入古人說詞")
        if len(text) > 4000:
            raise ValueError("單一聲音場景最多 4000 字")
        if not get_recitation_template(template_id):
            raise ValueError("請選擇古人說詞表演模板")
        if not get_bgm_preset(bgm_id):
            raise ValueError("背景音樂預設不存在")
        if not get_room_preset(room_id):
            raise ValueError("空間預設不存在")
        level = str(payload.get("musicLevel", "voice-first"))
        if level not in {"voice-first", "balanced", "cinematic"}:
            raise ValueError("配樂比例設定無效")
        return {
            "seedId": seed_id,
            "seedName": str(payload.get("seedName", "")).strip()[:120],
            "text": text,
            "recitationTemplateId": template_id,
            "bgmPresetId": bgm_id,
            "roomPresetId": room_id,
            "musicLevel": level,
            "introSeconds": max(0.0, min(8.0, float(payload.get("introSeconds", 1.4)))),
            "outroSeconds": max(0.5, min(12.0, float(payload.get("outroSeconds", 2.6)))),
            "mediaBgmJobId": SAFE_NAME.sub("", str(payload.get("mediaBgmJobId", "")))[:100],
        }

    @staticmethod
    def _decode_upload(data_url: str) -> tuple[str, bytes]:
        match = re.fullmatch(r"data:([^;,]+);base64,(.+)", str(data_url), flags=re.DOTALL)
        if not match or match.group(1) not in ALLOWED_BGM_MIME:
            raise ValueError("背景音樂請使用 WAV、MP3、M4A、AAC 或 OGG")
        try:
            audio = base64.b64decode(match.group(2), validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise ValueError("背景音樂資料損壞") from exc
        if not audio or len(audio) > 30 * 1024 * 1024:
            raise ValueError("背景音樂必須小於 30 MB")
        return ALLOWED_BGM_MIME[match.group(1)], audio

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = self._validate(payload)
        created = utc_now()
        identity = json.dumps({"created": created, "request": request}, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:10]
        scene_id = f"audio_scene_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{digest}"
        scene_dir = self.root / scene_id
        scene_dir.mkdir(parents=True, exist_ok=False)
        if str(payload.get("bgmDataUrl", "")).strip():
            extension, audio = self._decode_upload(str(payload["bgmDataUrl"]))
            upload_name = "uploaded_bgm" + extension
            (scene_dir / upload_name).write_bytes(audio)
            request.update({
                "uploadedBgmFile": upload_name,
                "uploadedBgmName": str(payload.get("bgmFileName", "自訂背景音樂"))[:160],
            })
        template = get_recitation_template(request["recitationTemplateId"]) or {}
        record = {
            "schemaVersion": 1,
            "id": scene_id,
            "title": str(payload.get("title", "")).strip()[:140] or f"{template.get('name', '古人說詞')}｜{request.get('seedName') or '聲音種子'}",
            "status": "queued",
            "stage": "等待聲音種子",
            "progress": 0.03,
            "error": None,
            "request": request,
            "result": None,
            "createdAt": created,
            "updatedAt": created,
            "startedAt": None,
            "finishedAt": None,
        }
        path = scene_dir / "job.json"
        atomic_json(path, record)
        self.executor.submit(self._run, scene_id)
        return scene_summary(record)

    def _set(self, path: Path, **changes: Any) -> dict[str, Any]:
        with self.lock:
            record = load_json(path, None)
            if not isinstance(record, dict):
                raise ValueError("聲音場景任務資料損壞")
            record.update(changes)
            record["updatedAt"] = utc_now()
            atomic_json(path, record)
            return record

    def _run(self, scene_id: str) -> None:
        path = self.root / scene_id / "job.json"
        try:
            record = self._set(path, status="running", stage="鎖定聲線並生成乾人聲", progress=0.12, startedAt=utc_now())
            voice_path, voice_result = self.voice_worker(dict(record["request"]))
            record = self._set(path, stage="套用古風空間與人聲修整", progress=0.58)
            template = get_recitation_template(record["request"]["recitationTemplateId"]) or {}
            scene_meta = {
                "id": scene_id,
                "title": record["title"],
                "createdAt": record["createdAt"],
                "text": record["request"]["text"],
                "seedId": record["request"]["seedId"],
                "recitation": {
                    "templateId": template.get("id"),
                    "templateName": template.get("name"),
                    "emotions": template.get("emotions", []),
                    "lineDirections": template.get("lineDirections", []),
                },
            }
            self._set(path, stage="配樂自動避讓與母帶輸出", progress=0.73)
            manifest = render_audio_scene(
                outputs=self.outputs,
                scene_dir=self.root / scene_id,
                voice_path=voice_path,
                request=record["request"],
                voice_metadata={
                    "seedId": record["request"]["seedId"],
                    "seedName": record["request"].get("seedName") or voice_result.get("seedName"),
                    "generationId": voice_result.get("id"),
                    "anchorId": voice_result.get("anchorId"),
                    "anchorLabel": voice_result.get("anchorLabel"),
                    "gender": voice_result.get("gender"),
                    "qualityGate": voice_result.get("qualityGate"),
                },
                scene_metadata=scene_meta,
            )
            manifest["seedName"] = record["request"].get("seedName") or voice_result.get("seedName")
            atomic_json(self.root / scene_id / "scene.json", manifest)
            self._set(path, status="completed", stage="可播放與下載", progress=1.0, result=manifest, finishedAt=utc_now(), error=None)
        except Exception as exc:
            detail = re.sub(r"\x1b\[[0-9;]*m", "", str(exc)).replace(str(self.outputs), "outputs")
            self._set(path, status="failed", stage="生成失敗", progress=1.0, error=f"{type(exc).__name__}: {detail[:900]}", finishedAt=utc_now())

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        records = []
        for path in self.root.glob("*/job.json"):
            record = load_json(path, None)
            if isinstance(record, dict):
                records.append(scene_summary(record))
        records.sort(key=lambda item: str(item.get("createdAt", "")), reverse=True)
        return records[:max(1, min(limit, 300))]

    def get(self, scene_id: str) -> dict[str, Any]:
        record = load_json(self._record_path(scene_id), None)
        if not isinstance(record, dict):
            raise ValueError("找不到指定聲音場景")
        return {**scene_summary(record), "request": record.get("request", {}), "result": record.get("result")}

    def retry(self, scene_id: str) -> dict[str, Any]:
        record = load_json(self._record_path(scene_id), None)
        if not isinstance(record, dict) or record.get("status") not in {"failed", "interrupted"}:
            raise ValueError("只有失敗或中斷的聲音場景能重試")
        payload = dict(record.get("request") or {})
        payload["title"] = f"重試｜{record.get('title', '古人說詞')}"
        upload = str(payload.get("uploadedBgmFile", ""))
        if upload:
            source = self.root / scene_id / upload
            mime = next((key for key, value in ALLOWED_BGM_MIME.items() if value == source.suffix.lower()), "audio/mpeg")
            payload["bgmDataUrl"] = f"data:{mime};base64,{base64.b64encode(source.read_bytes()).decode('ascii')}"
            payload["bgmFileName"] = payload.get("uploadedBgmName")
        return self.submit(payload)

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
