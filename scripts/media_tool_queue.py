#!/usr/bin/env python3
"""Durable media-audio utility queue for conversion and vocal separation."""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from audio_scene_mixer import atomic_json, utc_now
from media_audio_tools import SUPPORTED_INPUTS, convert_to_mp3, separate_vocals, separator_status


SAFE_ID = re.compile(r"[^a-zA-Z0-9_.-]+")


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def summary(record: dict[str, Any]) -> dict[str, Any]:
    result = record.get("result") if isinstance(record.get("result"), dict) else {}
    job_id = record.get("id")
    prefix = f"/media_audio_jobs/{job_id}/"
    outputs = result.get("outputs") if isinstance(result.get("outputs"), dict) else {}
    return {
        "id": job_id,
        "title": record.get("title"),
        "operation": record.get("operation"),
        "status": record.get("status"),
        "stage": record.get("stage"),
        "progress": record.get("progress", 0.0),
        "error": record.get("error"),
        "createdAt": record.get("createdAt"),
        "updatedAt": record.get("updatedAt"),
        "sourceName": record.get("sourceName"),
        "sourceMp3Url": prefix + outputs["sourceMp3"]["file"] if outputs.get("sourceMp3") else None,
        "bgmMp3Url": prefix + outputs["backgroundMusic"]["mp3"]["file"] if outputs.get("backgroundMusic") else None,
        "bgmWavUrl": prefix + outputs["backgroundMusic"]["wav"]["file"] if outputs.get("backgroundMusic") else None,
        "vocalsMp3Url": prefix + outputs["vocals"]["mp3"]["file"] if outputs.get("vocals") else None,
        "manifestUrl": prefix + "manifest.json" if record.get("status") == "completed" else None,
    }


class MediaToolQueue:
    def __init__(self, outputs: Path) -> None:
        self.outputs = outputs
        self.root = outputs / "media_audio_jobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="media-audio")
        self._recover_interrupted()

    def _recover_interrupted(self) -> None:
        for path in self.root.glob("*/job.json"):
            record = load_json(path, None)
            if isinstance(record, dict) and record.get("status") in {"queued", "running"}:
                record.update({
                    "status": "interrupted", "stage": "等待手動重試", "progress": 0.0,
                    "error": "工作站曾停止；請手動重試媒體處理。", "updatedAt": utc_now(),
                })
                atomic_json(path, record)

    @staticmethod
    def _decode_data_url(data_url: str, filename: str) -> tuple[str, bytes]:
        match = re.fullmatch(r"data:([^;,]+);base64,(.+)", str(data_url), flags=re.DOTALL)
        if not match:
            raise ValueError("媒體檔案資料格式無效")
        extension = Path(filename).suffix.lower()
        if extension not in SUPPORTED_INPUTS:
            guessed = mimetypes.guess_extension(match.group(1)) or ""
            extension = ".mp3" if guessed == ".mpga" else guessed
        if extension not in SUPPORTED_INPUTS:
            raise ValueError("支援 MP4、MOV、MKV、WebM、MP3、WAV、M4A、AAC、OGG、FLAC")
        try:
            raw = base64.b64decode(match.group(2), validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise ValueError("媒體檔案資料損壞") from exc
        if not raw or len(raw) > 180 * 1024 * 1024:
            raise ValueError("單一媒體檔案必須小於 180 MB")
        return extension, raw

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        operation = str(payload.get("operation", "extract_mp3"))
        if operation not in {"extract_mp3", "remove_vocals"}:
            raise ValueError("未知的媒體音訊操作")
        source_name = str(payload.get("fileName", "source.mp4")).strip()[:180] or "source.mp4"
        extension, raw = self._decode_data_url(str(payload.get("dataUrl", "")), source_name)
        if operation == "remove_vocals" and not separator_status()["available"]:
            raise RuntimeError("人聲分離模型尚未安裝；請先執行 python3 scripts/setup_audio_tools.py")
        created = utc_now()
        digest = hashlib.sha256(raw[:65536] + created.encode("utf-8")).hexdigest()[:10]
        job_id = f"media_audio_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{digest}"
        directory = self.root / job_id
        directory.mkdir(parents=True, exist_ok=False)
        source_file = "source" + extension
        (directory / source_file).write_bytes(raw)
        record = {
            "schemaVersion": 1,
            "id": job_id,
            "title": ("去人聲｜" if operation == "remove_vocals" else "轉 MP3｜") + source_name,
            "operation": operation,
            "sourceName": source_name,
            "sourceFile": source_file,
            "status": "queued",
            "stage": "等待媒體處理",
            "progress": 0.03,
            "error": None,
            "result": None,
            "createdAt": created,
            "updatedAt": created,
            "startedAt": None,
            "finishedAt": None,
        }
        atomic_json(directory / "job.json", record)
        self.executor.submit(self._run, job_id)
        return summary(record)

    def submit_local_path(self, path: Path, operation: str = "remove_vocals") -> dict[str, Any]:
        """Trusted CLI/server helper used for real local production validation."""
        path = path.resolve()
        if not path.is_file():
            raise ValueError("本機媒體檔案不存在")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return self.submit({
            "operation": operation,
            "fileName": path.name,
            "dataUrl": f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}",
        })

    def _set(self, path: Path, **changes: Any) -> dict[str, Any]:
        with self.lock:
            record = load_json(path, None)
            if not isinstance(record, dict):
                raise ValueError("媒體任務資料損壞")
            record.update(changes)
            record["updatedAt"] = utc_now()
            atomic_json(path, record)
            return record

    def _run(self, job_id: str) -> None:
        directory = self.root / job_id
        job_path = directory / "job.json"
        try:
            record = self._set(job_path, status="running", stage="抽取並轉換高品質 MP3", progress=0.18, startedAt=utc_now())
            source_mp3 = directory / "source_audio.mp3"
            source_info = convert_to_mp3(directory / record["sourceFile"], source_mp3)
            outputs: dict[str, Any] = {"sourceMp3": {"file": source_mp3.name, **source_info}}
            if record["operation"] == "remove_vocals":
                self._set(job_path, stage="AI 正在分離人聲與背景音樂", progress=0.43)
                separated = separate_vocals(source_mp3, directory)
                outputs.update({
                    "vocals": separated["vocals"],
                    "backgroundMusic": separated["backgroundMusic"],
                    "separation": {"engine": separated["engine"], "model": separated["model"]},
                })
            result = {
                "schemaVersion": 1,
                "id": job_id,
                "operation": record["operation"],
                "sourceName": record["sourceName"],
                "outputs": outputs,
                "completedAt": utc_now(),
            }
            atomic_json(directory / "manifest.json", result)
            self._set(job_path, status="completed", stage="可播放與下載", progress=1.0, result=result, error=None, finishedAt=utc_now())
        except Exception as exc:
            detail = re.sub(r"\x1b\[[0-9;]*m", "", str(exc)).replace(str(self.outputs), "outputs")
            self._set(job_path, status="failed", stage="處理失敗", progress=1.0, error=f"{type(exc).__name__}: {detail[:900]}", finishedAt=utc_now())

    def _path(self, job_id: str) -> Path:
        safe = SAFE_ID.sub("", str(job_id))[:100]
        path = self.root / safe / "job.json"
        record = load_json(path, None)
        if not isinstance(record, dict) or record.get("id") != job_id:
            raise ValueError("找不到指定媒體任務")
        return path

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        records = [load_json(path, None) for path in self.root.glob("*/job.json")]
        items = [summary(record) for record in records if isinstance(record, dict)]
        items.sort(key=lambda item: str(item.get("createdAt", "")), reverse=True)
        return items[:max(1, min(limit, 300))]

    def get(self, job_id: str) -> dict[str, Any]:
        record = load_json(self._path(job_id), None)
        return {**summary(record), "result": record.get("result")} if isinstance(record, dict) else {}

    def retry(self, job_id: str) -> dict[str, Any]:
        record = load_json(self._path(job_id), None)
        if not isinstance(record, dict) or record.get("status") not in {"failed", "interrupted"}:
            raise ValueError("只有失敗或中斷的媒體任務能重試")
        source = self.root / job_id / record["sourceFile"]
        mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        return self.submit({
            "operation": record["operation"], "fileName": record["sourceName"],
            "dataUrl": f"data:{mime};base64,{base64.b64encode(source.read_bytes()).decode('ascii')}",
        })

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
