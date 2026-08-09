#!/usr/bin/env python3
"""Durable asset layer for Voice Seed Studio.

The synthesis provider accepts one reference clip per request.  This module
turns that low-level primitive into a production asset: a passport, selectable
anchors, immutable versions, performance recipes, certification reports,
casting recommendations, continuity projects and portable voicepacks.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import struct
import urllib.parse
import wave
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import speaker_embedding


SAFE_ID = re.compile(r"[^a-zA-Z0-9_-]+")
GENDERS = {"女性", "男性", "中性／不指定", "不指定"}


PERFORMANCE_SEEDS: list[dict[str, Any]] = [
    {
        "id": "perf_intimate_reality",
        "name": "近景生活流",
        "category": "影視",
        "description": "像鏡頭已推到眼睛，只讓念頭、呼吸和細微重音被聽見。",
        "emotions": ["平靜", "欲言又止"],
        "intensity": "克制", "delivery": "電影對白", "pace": "標準",
        "pitch": "自然起伏", "pause": "自然停頓", "ending": "完整收句",
        "note": "先聽見對手，再開口；不朗誦、不展示情緒。",
        "anchorModes": ["neutral", "intimate"], "tags": ["近景", "真人感", "生活流"],
    },
    {
        "id": "perf_held_tears",
        "name": "忍住眼淚",
        "category": "情緒弧線",
        "description": "不是哭腔展示，而是努力把話說完，轉折處才讓氣息破一下。",
        "emotions": ["委屈", "哽咽", "動情"],
        "intensity": "克制", "delivery": "電影對白", "pace": "忽快忽慢",
        "pitch": "自然起伏", "pause": "長停頓", "ending": "情緒停住但不截斷",
        "note": "前段維持體面；真正重要的名字前停半拍。",
        "anchorModes": ["emotional", "intimate"], "tags": ["哭戲", "克制", "轉折"],
    },
    {
        "id": "perf_period_restraint",
        "name": "古裝含蓄",
        "category": "影視",
        "description": "權力與情感都藏在禮數之下，重點字落實，句尾不做統一下墜。",
        "emotions": ["壓抑的憤怒", "釋然"],
        "intensity": "明顯", "delivery": "古裝台詞", "pace": "忽快忽慢",
        "pitch": "先低後高", "pause": "句尾留白", "ending": "完整收句",
        "note": "不喊、不念腔；稱謂要有私人關係。",
        "anchorModes": ["authority", "emotional"], "tags": ["古裝", "權謀", "含蓄"],
    },
    {
        "id": "perf_thriller_whisper",
        "name": "懸疑低語",
        "category": "類型",
        "description": "恐懼藏在呼吸與觀察裡，資訊仍然清楚，最後一句落地。",
        "emotions": ["恐懼", "忐忑", "決絕"],
        "intensity": "明顯", "delivery": "低語耳語", "pace": "標準",
        "pitch": "偏低沉", "pause": "斷續哽咽", "ending": "完整收句",
        "note": "貼近麥克風但不要氣聲糊字；不要把恐懼演成尖叫。",
        "anchorModes": ["whisper", "intimate"], "tags": ["懸疑", "低語", "壓迫"],
    },
    {
        "id": "perf_comedy_bounce",
        "name": "喜劇節拍",
        "category": "類型",
        "description": "包袱前加速、落點後留白，角色始終相信自己正在做正經事。",
        "emotions": ["得意", "驚訝", "無奈"],
        "intensity": "自然", "delivery": "電影對白", "pace": "快速",
        "pitch": "自然起伏", "pause": "短停頓", "ending": "完整收句",
        "note": "不要刻意搞笑聲；笑點由節奏和資訊差完成。",
        "anchorModes": ["high_energy", "neutral"], "tags": ["喜劇", "節奏", "反差"],
    },
    {
        "id": "perf_authority_cold",
        "name": "冷靜掌控",
        "category": "角色",
        "description": "不靠音量取得權力，越重要越慢、越短、越準確。",
        "emotions": ["平靜", "決絕"],
        "intensity": "明顯", "delivery": "質問逼問", "pace": "標準",
        "pitch": "偏低沉", "pause": "短停頓", "ending": "完整收句",
        "note": "權力感來自不用證明自己；關鍵名詞清楚落下。",
        "anchorModes": ["authority", "neutral"], "tags": ["掌控", "職場", "反派"],
    },
    {
        "id": "perf_healing_night",
        "name": "深夜安撫",
        "category": "陪伴",
        "description": "像熟悉的人坐在旁邊，不急著解決，只先把對方接住。",
        "emotions": ["溫柔", "心疼", "欣慰"],
        "intensity": "克制", "delivery": "安撫哄勸", "pace": "慢速",
        "pitch": "自然", "pause": "長停頓", "ending": "尾音放輕",
        "note": "保留呼吸和微小不規則停頓；溫柔不是虛弱。",
        "anchorModes": ["intimate", "whisper"], "tags": ["治癒", "陪伴", "溫度"],
    },
    {
        "id": "perf_youth_spark",
        "name": "少年向前",
        "category": "角色",
        "description": "共鳴向前、句子帶動能，熱血但不靠破音與持續大喊。",
        "emotions": ["不甘", "勇氣", "喜悅"],
        "intensity": "強烈但不破音", "delivery": "舞台宣告", "pace": "快速",
        "pitch": "偏明亮", "pause": "短停頓", "ending": "完整收句",
        "note": "每句只有一個主重音；能量推向動詞。",
        "anchorModes": ["high_energy"], "tags": ["少年", "動畫", "熱血"],
    },
    {
        "id": "perf_confession_hesitant",
        "name": "猶豫告白",
        "category": "情緒弧線",
        "description": "先試探對方反應，再把最怕說出口的真話交出去。",
        "emotions": ["忐忑", "喜悅", "動情"],
        "intensity": "自然", "delivery": "電影對白", "pace": "忽快忽慢",
        "pitch": "自然起伏", "pause": "句尾留白", "ending": "欲言又止",
        "note": "前句可以快一點掩飾，最後問句微升等待回答。",
        "anchorModes": ["intimate", "emotional"], "tags": ["告白", "心動", "留白"],
    },
    {
        "id": "perf_documentary_warmth",
        "name": "有溫度旁白",
        "category": "敘事",
        "description": "知道故事的方向，但不是全知播報；讓每個畫面先在腦中出現。",
        "emotions": ["平靜", "共感", "希望"],
        "intensity": "自然", "delivery": "旁白敘事", "pace": "標準",
        "pitch": "自然起伏", "pause": "自然停頓", "ending": "完整收句",
        "note": "重點字自然加深，不讓每句成為同一個新聞句型。",
        "anchorModes": ["narration", "neutral"], "tags": ["旁白", "紀錄片", "故事"],
    },
    {
        "id": "perf_action_pressure",
        "name": "動作壓迫",
        "category": "類型",
        "description": "危機裡以短句傳遞決策；呼吸變急但資訊不能散。",
        "emotions": ["恐懼", "決絕"],
        "intensity": "強烈但不破音", "delivery": "舞台宣告", "pace": "快速",
        "pitch": "先低後高", "pause": "短停頓", "ending": "完整收句",
        "note": "動作發生在字與字之間；不要把整句都喊成同一音量。",
        "anchorModes": ["high_energy", "authority"], "tags": ["動作", "危機", "命令"],
    },
    {
        "id": "perf_broken_calm",
        "name": "平靜崩開",
        "category": "情緒弧線",
        "description": "前兩拍像已經接受，直到一個具體細節讓防線短暫裂開。",
        "emotions": ["平靜", "悲傷", "釋然"],
        "intensity": "克制", "delivery": "內心獨白", "pace": "慢速",
        "pitch": "先高後低", "pause": "長停頓", "ending": "情緒停住但不截斷",
        "note": "只在一個詞上失去控制，之後重新把話說完。",
        "anchorModes": ["emotional", "intimate"], "tags": ["層次", "崩潰", "克制"],
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_slug(value: str, fallback: str = "asset") -> str:
    cleaned = SAFE_ID.sub("_", str(value).strip()).strip("_").lower()
    return cleaned[:72] or fallback


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def atomic_write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data.encode("utf-8") if isinstance(data, str) else data
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def asset_id(prefix: str, payload: bytes = b"") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    digest = hashlib.sha256(payload + stamp.encode("ascii")).hexdigest()[:8]
    return f"{prefix}_{stamp}_{digest}"


def ensure_layout(outputs: Path) -> None:
    for name in ("performance_seeds", "casting_projects", "continuity_projects", "voicepacks", "quality_reports"):
        (outputs / name).mkdir(parents=True, exist_ok=True)


def _seed_dir(outputs: Path, seed_id: str) -> Path:
    directory = outputs / "voice_seeds" / safe_slug(seed_id)
    record = load_json(directory / "seed.json", None)
    if not isinstance(record, dict) or record.get("id") != seed_id:
        raise ValueError("找不到指定聲音種子")
    return directory


def _wav_duration(path: Path) -> float | None:
    if path.suffix.lower() != ".wav":
        return None
    try:
        with wave.open(str(path), "rb") as source:
            return round(source.getnframes() / source.getframerate(), 3) if source.getframerate() else 0.0
    except (OSError, wave.Error):
        return None


def ensure_passport(outputs: Path, seed_id: str) -> dict[str, Any]:
    directory = _seed_dir(outputs, seed_id)
    record = load_json(directory / "seed.json", {})
    passport_path = directory / "passport.json"
    passport = load_json(passport_path, None)
    if isinstance(passport, dict) and passport.get("seedId") == seed_id:
        return passport
    reference_file = str(record.get("referenceFile", "reference.wav"))
    anchor_id = f"anchor_{str(record.get('referenceSha256', 'legacy'))[:10]}"
    version_id = f"version_{str(record.get('referenceSha256', 'legacy'))[:10]}"
    passport = {
        "schemaVersion": 2,
        "seedId": seed_id,
        "identity": {
            "name": record.get("name", seed_id),
            "gender": record.get("gender", "不指定"),
            "kind": record.get("kind", "audio_clone"),
            "description": record.get("description", ""),
            "language": "zh-Hant / Mandarin",
            "status": "production",
        },
        "defaultAnchorId": anchor_id,
        "activeVersionId": version_id,
        "anchors": [{
            "id": anchor_id,
            "label": "原始主錨點",
            "mode": "neutral",
            "file": reference_file,
            "mime": record.get("referenceMime", "audio/wav"),
            "sha256": record.get("referenceSha256", ""),
            "bytes": record.get("referenceBytes", 0),
            "durationSeconds": _wav_duration(directory / reference_file),
            "createdAt": record.get("createdAt", utc_now()),
            "source": "legacy_reference",
        }],
        "versions": [{
            "id": version_id,
            "label": "原始版本",
            "anchorId": anchor_id,
            "parentVersionId": None,
            "notes": "由既有聲音種子自動建立的不可變基線。",
            "constraints": {"gender": record.get("gender", "不指定"), "preserveIdentity": True},
            "createdAt": record.get("createdAt", utc_now()),
        }],
        "createdAt": record.get("createdAt", utc_now()),
        "updatedAt": utc_now(),
    }
    atomic_write(passport_path, json.dumps(passport, ensure_ascii=False, indent=2) + "\n")
    return passport


def seed_asset(outputs: Path, seed_id: str) -> dict[str, Any]:
    directory = _seed_dir(outputs, seed_id)
    record = load_json(directory / "seed.json", {})
    passport = ensure_passport(outputs, seed_id)
    reports_dir = directory / "certifications"
    reports = []
    if reports_dir.exists():
        for path in sorted(reports_dir.glob("*.json"), reverse=True):
            report = load_json(path, None)
            if isinstance(report, dict):
                reports.append(report)
    active_version = next((item for item in passport["versions"] if item["id"] == passport.get("activeVersionId")), passport["versions"][0])
    anchors = []
    for anchor in passport.get("anchors", []):
        item = dict(anchor)
        item["audioUrl"] = f"/voice_seeds/{urllib.parse.quote(seed_id)}/{urllib.parse.quote(str(anchor['file']))}"
        anchors.append(item)
    return {
        "record": record,
        "passport": {**passport, "anchors": anchors},
        "activeVersion": active_version,
        "latestCertification": reports[0] if reports else None,
        "certifications": reports[:12],
    }


def seed_summaries(outputs: Path) -> list[dict[str, Any]]:
    seeds_root = outputs / "voice_seeds"
    result: list[dict[str, Any]] = []
    if not seeds_root.exists():
        return result
    for directory in sorted(seeds_root.iterdir(), reverse=True):
        record = load_json(directory / "seed.json", None) if directory.is_dir() else None
        if not isinstance(record, dict) or not record.get("id"):
            continue
        asset = seed_asset(outputs, str(record["id"]))
        passport = asset["passport"]
        latest = asset["latestCertification"]
        item = dict(record)
        active_version = asset["activeVersion"]
        preview_anchor = next(
            (anchor for anchor in passport["anchors"] if anchor.get("id") == active_version.get("anchorId")),
            passport["anchors"][0],
        )
        item.update({
            "audioUrl": preview_anchor["audioUrl"],
            "anchorCount": len(passport.get("anchors", [])),
            "versionCount": len(passport.get("versions", [])),
            "activeVersionId": passport.get("activeVersionId"),
            "certification": ({key: latest.get(key) for key in ("id", "score", "status", "createdAt")} if latest else None),
        })
        result.append(item)
    return result


def resolve_anchor(outputs: Path, seed_id: str, anchor_id: str = "", performance_tags: list[str] | None = None) -> tuple[dict[str, Any], dict[str, Any], Path]:
    asset = seed_asset(outputs, seed_id)
    passport = asset["passport"]
    anchors = passport.get("anchors", [])
    selected = next((item for item in anchors if item.get("id") == anchor_id), None) if anchor_id else None
    if not selected:
        active_version = asset["activeVersion"]
        selected = next((item for item in anchors if item.get("id") == active_version.get("anchorId")), None)
    wanted = {safe_slug(item) for item in (performance_tags or [])}
    if not anchor_id and wanted:
        matched = next((item for item in anchors if safe_slug(str(item.get("mode", ""))) in wanted), None)
        if matched:
            selected = matched
    if not selected:
        selected = anchors[0]
    path = _seed_dir(outputs, seed_id) / str(selected["file"])
    if not path.exists():
        raise ValueError("聲音錨點音檔不存在")
    return asset["record"], selected, path


def add_anchor(outputs: Path, seed_id: str, payload: dict[str, Any], mime: str, audio: bytes, extension: str) -> dict[str, Any]:
    directory = _seed_dir(outputs, seed_id)
    passport = ensure_passport(outputs, seed_id)
    sha = hashlib.sha256(audio).hexdigest()
    duplicate = next((item for item in passport["anchors"] if item.get("sha256") == sha), None)
    if duplicate:
        return seed_asset(outputs, seed_id)
    anchor_id = asset_id("anchor", audio)
    relative_file = f"anchors/{anchor_id}{extension}"
    atomic_write(directory / relative_file, audio)
    passport["anchors"].append({
        "id": anchor_id,
        "label": str(payload.get("label", "新錨點")).strip()[:80] or "新錨點",
        "mode": safe_slug(str(payload.get("mode", "neutral")), "neutral"),
        "file": relative_file,
        "mime": mime,
        "sha256": sha,
        "bytes": len(audio),
        "durationSeconds": _wav_duration(directory / relative_file),
        "createdAt": utc_now(),
        "source": "user_upload",
    })
    passport["updatedAt"] = utc_now()
    atomic_write(directory / "passport.json", json.dumps(passport, ensure_ascii=False, indent=2) + "\n")
    return seed_asset(outputs, seed_id)


def create_version(outputs: Path, seed_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    directory = _seed_dir(outputs, seed_id)
    passport = ensure_passport(outputs, seed_id)
    anchor_id = str(payload.get("anchorId", "")).strip() or str(passport.get("defaultAnchorId", ""))
    if not any(item.get("id") == anchor_id for item in passport["anchors"]):
        raise ValueError("版本指定的聲音錨點不存在")
    parent = str(passport.get("activeVersionId", "")) or None
    fingerprint = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    version_id = asset_id("version", fingerprint)
    passport["versions"].append({
        "id": version_id,
        "label": str(payload.get("label", "新版本")).strip()[:80] or "新版本",
        "anchorId": anchor_id,
        "parentVersionId": parent,
        "notes": str(payload.get("notes", "")).strip()[:1000],
        "constraints": {
            "gender": str(payload.get("gender") or passport["identity"].get("gender", "不指定")),
            "preserveIdentity": True,
            "allowedDrift": str(payload.get("allowedDrift", "strict")),
        },
        "createdAt": utc_now(),
    })
    passport["activeVersionId"] = version_id
    passport["updatedAt"] = utc_now()
    atomic_write(directory / "passport.json", json.dumps(passport, ensure_ascii=False, indent=2) + "\n")
    return seed_asset(outputs, seed_id)


def activate_version(outputs: Path, seed_id: str, version_id: str) -> dict[str, Any]:
    directory = _seed_dir(outputs, seed_id)
    passport = ensure_passport(outputs, seed_id)
    if not any(item.get("id") == version_id for item in passport["versions"]):
        raise ValueError("找不到指定聲音版本")
    passport["activeVersionId"] = version_id
    passport["updatedAt"] = utc_now()
    atomic_write(directory / "passport.json", json.dumps(passport, ensure_ascii=False, indent=2) + "\n")
    return seed_asset(outputs, seed_id)


def performance_seeds(outputs: Path) -> list[dict[str, Any]]:
    ensure_layout(outputs)
    custom = load_json(outputs / "performance_seeds" / "manifest.json", {"items": []})
    custom_items = custom.get("items", []) if isinstance(custom, dict) else []
    return [{**item, "builtin": True} for item in PERFORMANCE_SEEDS] + [
        {**item, "builtin": False} for item in custom_items if isinstance(item, dict)
    ]


def get_performance_seed(outputs: Path, performance_id: str) -> dict[str, Any] | None:
    return next((item for item in performance_seeds(outputs) if item.get("id") == performance_id), None)


def create_performance_seed(outputs: Path, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_layout(outputs)
    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValueError("表演種子需要名稱")
    fingerprint = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    item = {
        "id": asset_id("perf", fingerprint),
        "name": name[:80],
        "category": str(payload.get("category", "自訂")).strip()[:40] or "自訂",
        "description": str(payload.get("description", "")).strip()[:500],
        "emotions": list(dict.fromkeys(str(value).strip() for value in payload.get("emotions", []) if str(value).strip()))[:5],
        "intensity": str(payload.get("intensity", "自然")),
        "delivery": str(payload.get("delivery", "電影對白")),
        "pace": str(payload.get("pace", "標準")),
        "pitch": str(payload.get("pitch", "自然起伏")),
        "pause": str(payload.get("pause", "自然停頓")),
        "ending": str(payload.get("ending", "完整收句")),
        "note": str(payload.get("note", "")).strip()[:500],
        "anchorModes": [safe_slug(str(value)) for value in payload.get("anchorModes", []) if str(value).strip()][:4],
        "tags": list(dict.fromkeys(str(value).strip() for value in payload.get("tags", []) if str(value).strip()))[:8],
        "createdAt": utc_now(),
    }
    path = outputs / "performance_seeds" / "manifest.json"
    manifest = load_json(path, {"schemaVersion": 1, "items": []})
    if not isinstance(manifest, dict):
        manifest = {"schemaVersion": 1, "items": []}
    manifest.setdefault("items", []).append(item)
    manifest["updatedAt"] = utc_now()
    atomic_write(path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return item


def audio_signature(path: Path) -> dict[str, Any] | None:
    if path.suffix.lower() != ".wav":
        return None
    try:
        with wave.open(str(path), "rb") as source:
            channels, width, rate, frames = source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getnframes()
            raw = source.readframes(frames)
    except (OSError, wave.Error):
        return None
    if width != 2 or not raw or not rate:
        return {"supported": False, "durationSeconds": round(frames / rate, 3) if rate else 0.0}
    samples = struct.unpack("<" + "h" * (len(raw) // 2), raw)
    if channels > 1:
        samples = samples[::channels]
    count = max(1, len(samples))
    peak = max(abs(value) for value in samples)
    rms = math.sqrt(sum(value * value for value in samples) / count)
    crossings = sum(1 for left, right in zip(samples, samples[1:]) if (left < 0 <= right) or (right < 0 <= left))
    window = max(1, int(rate * 0.02))
    energies = []
    for start in range(0, len(samples), window):
        chunk = samples[start:start + window]
        energies.append(math.sqrt(sum(value * value for value in chunk) / max(1, len(chunk))))
    silence_threshold = max(96.0, peak * 0.012)
    silence_ratio = sum(energy < silence_threshold for energy in energies) / max(1, len(energies))
    clipping_ratio = sum(abs(value) >= 32700 for value in samples) / count
    return {
        "supported": True,
        "durationSeconds": round(len(samples) / rate, 3),
        "sampleRate": rate,
        "rmsDbfs": round(20 * math.log10(max(rms, 1.0) / 32768), 2),
        "peakDbfs": round(20 * math.log10(max(peak, 1) / 32768), 2),
        "zeroCrossingRate": round(crossings / count, 5),
        "silenceRatio": round(silence_ratio, 4),
        "clippingRatio": round(clipping_ratio, 6),
    }


def acoustic_similarity(reference: dict[str, Any] | None, take: dict[str, Any] | None) -> float | None:
    if not reference or not take or not reference.get("supported") or not take.get("supported"):
        return None
    rms_delta = min(1.0, abs(float(reference["rmsDbfs"]) - float(take["rmsDbfs"])) / 24.0)
    zcr_base = max(0.005, float(reference["zeroCrossingRate"]))
    zcr_delta = min(1.0, abs(float(reference["zeroCrossingRate"]) - float(take["zeroCrossingRate"])) / (zcr_base * 3.0))
    silence_delta = min(1.0, abs(float(reference["silenceRatio"]) - float(take["silenceRatio"])) / 0.8)
    return round(max(0.0, 100.0 * (1.0 - 0.35 * rms_delta - 0.45 * zcr_delta - 0.20 * silence_delta)), 1)


def certify_seed(outputs: Path, seed_id: str) -> dict[str, Any]:
    asset = seed_asset(outputs, seed_id)
    record, anchor, reference_path = resolve_anchor(outputs, seed_id)
    reference = audio_signature(reference_path)
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, points: int, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "points": points if passed else 0, "maxPoints": points, "detail": detail})

    duration = float((reference or {}).get("durationSeconds", 0.0))
    check("參考長度", 2.0 <= duration <= 45.0, 12, f"{duration:.2f}s；建議 2–45 秒")
    clip = float((reference or {}).get("clippingRatio", 1.0))
    check("無削波", clip < 0.003, 10, f"削波比例 {clip * 100:.3f}%")
    silence = float((reference or {}).get("silenceRatio", 1.0))
    check("有效人聲密度", silence < 0.55, 8, f"靜音比例 {silence * 100:.1f}%")
    gender = str(record.get("gender", "不指定"))
    check("選角硬鎖", gender in {"女性", "男性"}, 10, f"性別鎖定：{gender}")
    check("版本血統", bool(asset["passport"].get("activeVersionId")), 10, f"{len(asset['passport'].get('versions', []))} 個版本")
    check("多錨點可用", len(asset["passport"].get("anchors", [])) >= 2, 10, f"{len(asset['passport'].get('anchors', []))} 個錨點")

    manifest = load_json(outputs / "voice_generations" / "manifest.json", {"samples": []})
    samples = [item for item in manifest.get("samples", []) if isinstance(item, dict) and item.get("seedId") == seed_id][-12:] if isinstance(manifest, dict) else []
    guarded = sum(1 for item in samples if float(item.get("durationSeconds", 0)) <= float(item.get("originalDurationSeconds", item.get("durationSeconds", 0))) + 0.1)
    check("長度護欄", bool(samples) and guarded == len(samples), 10, f"{guarded}/{len(samples)} 個 take 合理")
    emotion_coverage = len({emotion for item in samples for emotion in item.get("tags", []) if emotion not in {"聲音種子", "影視配音"}})
    check("表演覆蓋", emotion_coverage >= 4, 10, f"覆蓋 {emotion_coverage} 種表演標籤")

    similarities = []
    embedding_results = []
    for item in samples[-6:]:
        take_path = outputs / "voice_generations" / str(item.get("file", ""))
        score = acoustic_similarity(reference, audio_signature(take_path)) if take_path.exists() else None
        if score is not None:
            similarities.append(score)
        if take_path.exists():
            embedding = speaker_embedding.compare(reference_path, take_path)
            if embedding.get("available") and embedding.get("score") is not None:
                embedding_results.append(embedding)
    average_similarity = round(sum(similarities) / len(similarities), 1) if similarities else None
    embedding_score = round(
        sum(float(item["score"]) for item in embedding_results) / len(embedding_results), 1
    ) if embedding_results else None
    embedding_cosine = round(
        sum(float(item["cosineSimilarity"]) for item in embedding_results) / len(embedding_results), 6
    ) if embedding_results else None
    if embedding_score is not None:
        check(
            "WeSpeaker 聲紋一致性",
            all(item.get("decision") == "pass" for item in embedding_results),
            20,
            f"平均 cosine {embedding_cosine:.6f} · 分數 {embedding_score}/100 · {len(embedding_results)} 個 take",
        )
    else:
        check(
            "聲學一致性（後備）",
            average_similarity is not None and average_similarity >= 62,
            20,
            f"聲學輪廓 {average_similarity if average_similarity is not None else '無資料'} / 100；embedding 尚不可用",
        )

    score = sum(item["points"] for item in checks)
    status = "certified" if score >= 80 else "review" if score >= 60 else "blocked"
    report_id = asset_id("cert", f"{seed_id}:{score}".encode("utf-8"))
    report = {
        "schemaVersion": 1,
        "id": report_id,
        "seedId": seed_id,
        "seedName": record.get("name", seed_id),
        "versionId": asset["passport"].get("activeVersionId"),
        "anchorId": anchor.get("id"),
        "score": score,
        "status": status,
        "checks": checks,
        "referenceSignature": reference,
        "acousticSimilarity": average_similarity,
        "speakerEmbedding": {
            "available": bool(embedding_results),
            "provider": "wespeaker-cnceleb-resnet34-onnx" if embedding_results else "fallback",
            "score": embedding_score,
            "cosineSimilarity": embedding_cosine,
            "sampleCount": len(embedding_results),
            "embeddingDimensions": embedding_results[0].get("embeddingDimensions") if embedding_results else None,
        },
        "takeCount": len(samples),
        "createdAt": utc_now(),
        "method": "local-signal-gate-v1",
    }
    report_path = _seed_dir(outputs, seed_id) / "certifications" / f"{report_id}.json"
    atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    atomic_write(outputs / "quality_reports" / f"{report_id}.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def export_voicepack(outputs: Path, seed_id: str) -> dict[str, Any]:
    ensure_layout(outputs)
    asset = seed_asset(outputs, seed_id)
    directory = _seed_dir(outputs, seed_id)
    pack_name = f"{safe_slug(str(asset['record'].get('name', seed_id)))}_{safe_slug(seed_id)}.voicepack"
    target = outputs / "voicepacks" / pack_name
    manifest = {
        "schemaVersion": 1,
        "format": "voice-seed-pack",
        "seedId": seed_id,
        "name": asset["record"].get("name", seed_id),
        "exportedAt": utc_now(),
        "activeVersionId": asset["passport"].get("activeVersionId"),
        "fileCount": 0,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        candidates = [directory / "seed.json", directory / "passport.json"]
        for anchor in asset["passport"].get("anchors", []):
            candidates.append(directory / str(anchor.get("file", "")))
        certs = directory / "certifications"
        if certs.exists():
            candidates.extend(sorted(certs.glob("*.json")))
        written = set()
        for path in candidates:
            if not path.exists() or path in written:
                continue
            archive.write(path, path.relative_to(directory).as_posix())
            written.add(path)
        manifest["fileCount"] = len(written)
        archive.writestr("voicepack.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    atomic_write(target, buffer.getvalue())
    return {**manifest, "url": f"/voicepacks/{urllib.parse.quote(pack_name)}", "bytes": target.stat().st_size}


def recommend_cast(outputs: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    gender = str(payload.get("gender", "不指定")).strip()
    brief = " ".join(str(payload.get(key, "")) for key in ("role", "age", "traits", "genre", "text")).lower()
    wanted_performances = [str(item) for item in payload.get("performanceIds", [])]
    performance_tags = {
        tag.lower() for performance_id in wanted_performances
        for perf in [get_performance_seed(outputs, performance_id)] if perf
        for tag in [perf.get("name", ""), *perf.get("tags", [])]
    }
    results = []
    for seed in seed_summaries(outputs):
        haystack = " ".join(str(seed.get(key, "")) for key in ("name", "description", "gender")).lower()
        score = 34 if gender in {"女性", "男性"} and seed.get("gender") == gender else 8 if gender not in {"女性", "男性"} else -24
        reasons = ["性別硬鎖吻合" if score >= 34 else "未指定性別限制" if score >= 8 else "性別條件不符"]
        keyword_groups = {
            "年輕／少女／少年": ["年輕", "少女", "少年", "青春", "蘿莉"],
            "成熟／權威": ["成熟", "御姐", "低沉", "權臣", "將軍", "指揮官", "可靠"],
            "甜美／溫柔": ["甜", "溫柔", "治癒", "暖", "鄰家", "戀人"],
            "懸疑／冷感": ["懸疑", "低語", "冷", "神秘", "恐懼"],
            "旁白／敘事": ["旁白", "說書", "故事", "主持"],
        }
        for label, keywords in keyword_groups.items():
            if any(word in brief for word in keywords) and any(word in haystack for word in keywords):
                score += 13
                reasons.append(f"{label}語意吻合")
        mature_words = ("成熟", "中年", "可靠", "權威", "御姐", "將軍")
        young_words = ("年輕", "少女", "少年", "青春", "蘿莉", "童聲")
        if any(word in brief for word in mature_words) and any(word in haystack for word in young_words):
            score -= 18
            reasons.append("年齡感可能過輕")
        if any(word in brief for word in young_words) and any(word in haystack for word in mature_words):
            score -= 18
            reasons.append("年齡感可能過熟")
        overlaps = [tag for tag in performance_tags if tag and tag in haystack]
        score += min(14, len(overlaps) * 5)
        if overlaps:
            reasons.append("表演需求與聲線描述相符")
        certification = seed.get("certification") or {}
        if certification.get("status") == "certified":
            score += 12
            reasons.append("已通過保真認證")
        elif certification:
            score += int(certification.get("score", 0)) // 15
        score += min(8, max(0, int(seed.get("anchorCount", 1)) - 1) * 4)
        if int(seed.get("anchorCount", 1)) > 1:
            reasons.append("具多錨點切換")
        results.append({"seed": seed, "score": max(0, min(100, score)), "reasons": reasons[:4]})
    results.sort(key=lambda item: (item["score"], str(item["seed"].get("createdAt", ""))), reverse=True)
    return results[:8]


def continuity_projects(outputs: Path) -> list[dict[str, Any]]:
    ensure_layout(outputs)
    projects = []
    for directory in sorted((outputs / "continuity_projects").iterdir(), reverse=True):
        item = load_json(directory / "project.json", None) if directory.is_dir() else None
        if isinstance(item, dict):
            projects.append(item)
    return projects


def save_continuity_project(outputs: Path, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_layout(outputs)
    title = str(payload.get("title", "")).strip()
    if not title:
        raise ValueError("連戲專案需要名稱")
    project_id = safe_slug(str(payload.get("id", "")), "") or asset_id("continuity", title.encode("utf-8"))
    existing = load_json(outputs / "continuity_projects" / project_id / "project.json", {})
    created = existing.get("createdAt", utc_now()) if isinstance(existing, dict) else utc_now()
    roles = payload.get("roles", {}) if isinstance(payload.get("roles"), dict) else {}
    beats = payload.get("beats", []) if isinstance(payload.get("beats"), list) else []
    project = {
        "schemaVersion": 1,
        "id": project_id,
        "title": title[:120],
        "format": str(payload.get("format", "短劇"))[:40],
        "genre": str(payload.get("genre", "劇情"))[:60],
        "logline": str(payload.get("logline", ""))[:500],
        "roles": roles,
        "beats": beats[:80],
        "status": str(payload.get("status", "draft")),
        "createdAt": created,
        "updatedAt": utc_now(),
    }
    directory = outputs / "continuity_projects" / project_id
    atomic_write(directory / "project.json", json.dumps(project, ensure_ascii=False, indent=2) + "\n")
    export = {
        "project": {key: project[key] for key in ("id", "title", "format", "genre", "logline")},
        "cast": roles,
        "timeline": beats,
        "exportedAt": utc_now(),
    }
    atomic_write(directory / "production_manifest.json", json.dumps(export, ensure_ascii=False, indent=2) + "\n")
    project["manifestUrl"] = f"/continuity_projects/{urllib.parse.quote(project_id)}/production_manifest.json"
    return project


def studio_overview(outputs: Path) -> dict[str, Any]:
    seeds = seed_summaries(outputs)
    performances = performance_seeds(outputs)
    projects = continuity_projects(outputs)
    generation_manifest = load_json(outputs / "voice_generations" / "manifest.json", {"samples": []})
    generations = generation_manifest.get("samples", []) if isinstance(generation_manifest, dict) else []
    scenes = load_json(outputs / "dialogue_scenes" / "manifest.json", {"scenes": []})
    scene_items = scenes.get("scenes", []) if isinstance(scenes, dict) else []
    certified = sum(1 for seed in seeds if (seed.get("certification") or {}).get("status") == "certified")
    review = sum(1 for seed in seeds if seed.get("certification") and (seed.get("certification") or {}).get("status") != "certified")
    return {
        "counts": {
            "seeds": len(seeds), "multiAnchor": sum(int(seed.get("anchorCount", 0)) > 1 for seed in seeds),
            "certified": certified, "review": review, "performances": len(performances),
            "generations": len(generations), "scenes": len(scene_items), "projects": len(projects),
        },
        "seeds": seeds,
        "performances": performances,
        "projects": projects,
        "recentGenerations": list(reversed(generations[-18:])),
        "recentScenes": scene_items[:8],
        "speakerEmbedding": speaker_embedding.runtime_status(),
        "capabilities": ["聲音護照", "多錨點", "版本血統", "表演種子", "WeSpeaker 聲紋", "保真門禁", "角色選角", "場景連戲", "voicepack"],
    }
