#!/usr/bin/env python3
"""Local Voice Seed Studio API and static-file server.

The browser never receives MIMO_API_KEY.  It talks to this localhost process,
which stores seed references and calls MiMo's voice-design/voice-clone models.
"""

from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import mimetypes
import os
import re
import sys
import struct
import urllib.parse
import wave
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any

from generate_tts_catalog import load_local_env
from paths import resolve_workspace_root
from providers.mimo import DEFAULT_BASE_URL, MimoRequestError, request_audio


ROOT = resolve_workspace_root()
OUTPUTS = ROOT / "outputs"
SEEDS = OUTPUTS / "voice_seeds"
GENERATIONS = OUTPUTS / "voice_generations"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
SAFE_ID = re.compile(r"[^a-zA-Z0-9_-]+")
EMOTIONS = ["怅然", "欣慰", "得意", "無奈", "愧疚", "釋然", "嫉妒", "厭倦", "忐忑", "動情"]
GENDERS = {"女性", "男性", "中性／不指定", "不指定"}
DELIVERIES = {"電影對白", "古裝台詞", "內心獨白", "旁白敘事", "低語耳語", "舞台宣告", "質問逼問", "安撫哄勸"}
PACES = {"慢速", "標準", "快速", "忽快忽慢"}
PITCHES = {"自然", "自然起伏", "偏低沉", "偏明亮", "先低後高", "先高後低"}
PAUSES = {"自然停頓", "短停頓", "長停頓", "句尾留白", "斷續哽咽"}
ENDINGS = {"完整收句", "尾音放輕", "欲言又止", "情緒停住但不截斷"}
HUMAN_VOICE_GUIDANCE = (
    "自然人聲要求：像真人在同一個房間一次錄製，保留自然呼吸、微小而不規則的停頓、"
    "口語連貫與細微強弱變化；重點字可以輕輕加深，但不要每字等長等重、不要機械升降、"
    "不要客服播報腔、不要過度完美的合成感。最重要的是不要讓每一句都用同一個下墜尾音："
    "疑問句要保留上揚的等待感，感嘆句向前推，省略號懸住，逗號只停不收，完整陳述句才自然微降；"
    "句尾收法要有變化，不能整段像同一條機械波形。"
)


def prosody_map(text: str) -> str:
    """Describe sentence-level intonation so Mandarin does not fall at every end.

    MiMo is very good at preserving a timbre but tends to normalize short Chinese
    takes into the same declarative contour.  Giving it a compact, punctuation-
    aware score is more reliable than repeating generic words such as "有情緒".
    The score stays in the non-spoken context and never changes the dialogue.
    """
    pieces = [piece.strip() for piece in re.findall(r"[^。！？!?…；;，,\n]+[。！？!?…；;，,]?", text) if piece.strip()]
    if not pieces:
        return "語調提示：保持自然起伏，不要讓結尾全部下墜。"
    rows: list[str] = []
    declarative_turn = 0
    for index, piece in enumerate(pieces[:12], start=1):
        punctuation = piece[-1] if piece[-1] in "。！？!?…；;，," else ""
        if punctuation in {"？", "?"}:
            rule = "尾音短促上揚，像在等對方回答；不要下墜"
        elif punctuation in {"！", "!"}:
            rule = "重音向前推，尾端保持能量或微微上提；不要拖長"
        elif punctuation in {"…"}:
            rule = "音高懸住，保留未說完的空間；不要收成低音"
        elif punctuation in {"，", ",", "；", ";"}:
            rule = "只停頓不收句，保持中段音高，讓下一句接得起來"
        else:
            options = ("自然微降但不拉長", "平收、不要刻意下壓", "尾端微升後停住")
            rule = options[declarative_turn % len(options)]
            declarative_turn += 1
        rows.append(f"{index}. {punctuation or '未完'}：{rule}")
    return "逐句語調走位（只作表演指令，不要朗讀）：" + "；".join(rows) + "。"


def normalize_gender(value: Any) -> str:
    """Normalize the user-facing gender lock without guessing from a name."""
    value = str(value or "不指定").strip()
    return value if value in GENDERS else "不指定"


def gender_instruction(gender: str) -> str:
    if gender == "女性":
        return "性別硬性要求：輸出必須是女性聲線；不得出現男性低沉共鳴、男性音色或男性年齡特徵。"
    if gender == "男性":
        return "性別硬性要求：輸出必須是男性聲線；不得出現女性高亮共鳴、女性音色或女性年齡特徵。"
    return "性別不強制指定，但請保持參考音檔原本的性別與年齡特徵。"


def normalize_option(value: Any, allowed: set[str], fallback: str) -> str:
    value = str(value or fallback).strip()
    return value if value in allowed else fallback


def pitch_instruction(value: str) -> str:
    return {
        "自然": "跟著標點與語意自然起伏，不能每句同一個方向",
        "自然起伏": "讓疑問、感嘆、懸置和陳述各自有不同曲線",
        "偏低沉": "只降低共鳴位置，不代表每句尾音都下降",
        "偏明亮": "保持明亮前置共鳴，句尾仍依標點變化",
        "先低後高": "整段由低到高，但每句內仍要有上揚、平收與微降的差異",
        "先高後低": "整段由高到低，但不要把每個句尾都拉低",
    }.get(value, "依標點自然起伏，不要統一下墜")


def ending_instruction(value: str) -> str:
    return {
        "完整收句": "完整不拖長；只有陳述句可自然微降，問句與感嘆句仍要保留各自語調",
        "尾音放輕": "放輕的是音量與力道，不是把音高往下拉；可以平收或微升",
        "欲言又止": "最後一字停住或微升，留下未說完感，不要低沉拖尾",
        "情緒停住但不截斷": "在情緒位置懸住，保持氣息連續，不要做制式下降",
    }.get(value, "依標點完成收句，不要每句下墜")


def wav_duration(audio: bytes) -> float:
    """Read a WAV duration without writing a temporary file."""
    with wave.open(io.BytesIO(audio), "rb") as stream:
        return stream.getnframes() / stream.getframerate() if stream.getframerate() else 0.0


def duration_limit(text: str) -> float:
    """Keep generated speech proportional to the amount of written dialogue."""
    spoken_chars = len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", text))
    return max(8.0, min(52.0, 4.0 + spoken_chars * 0.65))


def trim_wav(audio: bytes, max_seconds: float) -> tuple[bytes, float]:
    """Trim leading/trailing silence and enforce a safe upper bound."""
    with wave.open(io.BytesIO(audio), "rb") as source:
        params = source.getparams()
        raw = source.readframes(source.getnframes())
    if not params.framerate or not params.sampwidth or not raw:
        return audio, wav_duration(audio)
    frame_bytes = params.nchannels * params.sampwidth
    total_frames = len(raw) // frame_bytes
    if total_frames <= int(max_seconds * params.framerate):
        return audio, total_frames / params.framerate
    # Use a conservative RMS gate to locate actual speech.  If the model
    # repeats a very short line for minutes, the hard cap below still keeps the
    # first complete take usable instead of shipping a 1–2 minute file.
    window = max(1, int(params.framerate * 0.1))
    peak = 0
    energies: list[float] = []
    for index in range(0, total_frames, window):
        chunk = raw[index * frame_bytes : min(total_frames, index + window) * frame_bytes]
        if params.sampwidth == 2:
            values = struct.unpack("<" + "h" * (len(chunk) // 2), chunk)
            peak = max(peak, max((abs(value) for value in values), default=0))
            energies.append((sum(value * value for value in values) / max(1, len(values))) ** 0.5)
        else:
            energies.append(1.0 if any(chunk) else 0.0)
    threshold = max(80.0, peak * 0.008)
    active = [index for index, energy in enumerate(energies) if energy >= threshold]
    start = max(0, (active[0] * window - int(params.framerate * 0.15)) if active else 0)
    end = min(total_frames, ((active[-1] + 1) * window + int(params.framerate * 0.35)) if active else total_frames)
    max_frames = int(max_seconds * params.framerate)
    if end - start > max_frames:
        end = min(total_frames, start + max_frames)
    clipped = raw[start * frame_bytes : end * frame_bytes]
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setparams(params)
        target.writeframes(clipped)
    return output.getvalue(), len(clipped) / frame_bytes / params.framerate


def safe_slug(value: str, fallback: str = "seed") -> str:
    value = SAFE_ID.sub("_", value.strip()).strip("_").lower()
    return value[:64] or fallback


def atomic_write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data.encode("utf-8") if isinstance(data, str) else data
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def now_id(prefix: str, name: str, payload: bytes) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    digest = hashlib.sha256(payload).hexdigest()[:10]
    return f"{prefix}_{stamp}_{safe_slug(name)}_{digest}"


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def seed_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not SEEDS.exists():
        return records
    for directory in sorted(SEEDS.iterdir(), key=lambda path: path.name, reverse=True):
        if not directory.is_dir():
            continue
        record = load_json(directory / "seed.json", None)
        if not isinstance(record, dict) or not record.get("id"):
            continue
        record = dict(record)
        record["audioUrl"] = f"/voice_seeds/{urllib.parse.quote(directory.name)}/{urllib.parse.quote(record.get('referenceFile', 'reference.wav'))}"
        records.append(record)
    return records


def decode_data_url(data_url: str) -> tuple[str, bytes]:
    if not isinstance(data_url, str) or not data_url.startswith("data:"):
        raise ValueError("請提供 WAV 或 MP3 的 data URL")
    header, separator, encoded = data_url.partition(",")
    if separator != "," or ";base64" not in header:
        raise ValueError("音檔格式不是 Base64 data URL")
    mime = header[5:].split(";", 1)[0].lower()
    allowed = {"audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp3"}
    if mime not in allowed:
        raise ValueError("只接受 WAV 或 MP3")
    if len(data_url) > MAX_UPLOAD_BYTES * 1.4:
        raise ValueError("參考音檔 Base64 不能超過 10 MB")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("音檔 Base64 無法解析") from exc
    if not payload or len(payload) > MAX_UPLOAD_BYTES:
        raise ValueError("參考音檔不能為空，且不能超過 10 MB")
    if mime in {"audio/wav", "audio/x-wav"} and not payload[:4] == b"RIFF":
        raise ValueError("WAV 檔案標頭無效")
    if mime in {"audio/mpeg", "audio/mp3"} and not (payload[:3] == b"ID3" or payload[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}):
        raise ValueError("MP3 檔案標頭無效")
    return mime, payload


def mime_extension(mime: str) -> str:
    return ".wav" if mime in {"audio/wav", "audio/x-wav"} else ".mp3"


def api_key_and_base_url() -> tuple[str, str]:
    load_local_env(ROOT)
    key = os.environ.get("MIMO_API_KEY", "")
    if not key:
        raise RuntimeError("MIMO_API_KEY 未設定，請檢查 scripts/.env")
    return key, os.environ.get("MIMO_BASE_URL", DEFAULT_BASE_URL)


def create_text_seed(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    description = str(payload.get("description", "")).strip()
    gender = normalize_gender(payload.get("gender"))
    reference_text = str(payload.get("referenceText", "你好，這是我的固定聲音種子。之後請保持同一個聲線。"))[:2000].strip()
    if not name or not description:
        raise ValueError("文字建種需要名稱與聲音描述")
    locked_description = (
        f"{gender_instruction(gender)} {description} "
        f"{HUMAN_VOICE_GUIDANCE} 請把性別當成不可違反的演員選角條件，並保持年齡、共鳴位置與說話習慣一致。"
    )
    api_key, base_url = api_key_and_base_url()
    audio = request_audio(
        api_key=api_key,
        base_url=base_url,
        model="mimo-v2.5-tts-voicedesign",
        context=locked_description,
        text=reference_text,
        audio_format="wav",
        timeout=180.0,
        retries=2,
    )
    return save_seed(
        name=name,
        kind="text_design",
        description=locked_description,
        reference_text=reference_text,
        mime="audio/wav",
        audio=audio,
        model="mimo-v2.5-tts-voicedesign",
        gender=gender,
    )


def create_audio_seed(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    gender = normalize_gender(payload.get("gender"))
    if not name:
        raise ValueError("上傳建種需要名稱")
    mime, audio = decode_data_url(str(payload.get("dataUrl", "")))
    return save_seed(
        name=name,
        kind="audio_clone",
        description=f"{gender_instruction(gender)} 使用者上傳的固定參考音檔。",
        reference_text=str(payload.get("referenceText", "")).strip()[:2000],
        mime=mime,
        audio=audio,
        model="mimo-v2.5-tts-voiceclone",
        gender=gender,
    )


def save_seed(*, name: str, kind: str, description: str, reference_text: str, mime: str, audio: bytes, model: str, gender: str) -> dict[str, Any]:
    seed_id = now_id("seed", name, audio)
    directory = SEEDS / seed_id
    directory.mkdir(parents=True, exist_ok=False)
    extension = mime_extension(mime)
    reference_file = f"reference{extension}"
    atomic_write(directory / reference_file, audio)
    record = {
        "schemaVersion": 1,
        "id": seed_id,
        "name": name,
        "kind": kind,
        "gender": normalize_gender(gender),
        "description": description,
        "referenceText": reference_text,
        "model": model,
        "referenceFile": reference_file,
        "referenceMime": mime,
        "referenceBytes": len(audio),
        "referenceSha256": hashlib.sha256(audio).hexdigest(),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
    }
    atomic_write(directory / "seed.json", json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    record["audioUrl"] = f"/voice_seeds/{urllib.parse.quote(seed_id)}/{urllib.parse.quote(reference_file)}"
    return record


def generate_from_seed(payload: dict[str, Any]) -> dict[str, Any]:
    seed_id = str(payload.get("seedId", "")).strip()
    text = str(payload.get("text", "")).strip()
    emotions = [str(item).strip() for item in payload.get("emotions", []) if str(item).strip()]
    intensity = str(payload.get("intensity", "自然")).strip() or "自然"
    delivery = normalize_option(payload.get("delivery"), DELIVERIES, "電影對白")
    pace = normalize_option(payload.get("pace"), PACES, "標準")
    pitch = normalize_option(payload.get("pitch"), PITCHES, "自然")
    pause = normalize_option(payload.get("pause"), PAUSES, "自然停頓")
    ending = normalize_option(payload.get("ending"), ENDINGS, "完整收句")
    performance_note = str(payload.get("performanceNote", "")).strip()[:500]
    if not seed_id or not text:
        raise ValueError("生成語音需要聲音種子與台詞")
    if len(text) > 8000:
        raise ValueError("單次台詞最多 8000 字")
    emotions = list(dict.fromkeys(emotions))[:5]
    seed_dir = SEEDS / safe_slug(seed_id)
    record = load_json(seed_dir / "seed.json", None)
    if not isinstance(record, dict) or record.get("id") != seed_id:
        raise ValueError("找不到指定聲音種子")
    gender = normalize_gender(record.get("gender"))
    reference_file = str(record.get("referenceFile", ""))
    reference_path = seed_dir / reference_file
    if not reference_path.exists():
        raise ValueError("聲音種子的參考音檔不存在")
    reference_audio = reference_path.read_bytes()
    mime = str(record.get("referenceMime", "audio/wav"))
    voice_data_url = f"data:{mime};base64,{base64.b64encode(reference_audio).decode('ascii')}"
    emotion_line = "、".join(emotions) if emotions else "平靜"
    context = (
        "這是一個已鎖定的聲音種子。請保持參考音檔的音色身份、年齡、性別、共鳴位置、"
        "口音與說話習慣，不要重新設計聲線。只改變本次指定的表演情緒。"
        f"{gender_instruction(gender)} 若參考音檔與性別設定衝突，請優先遵守性別設定；"
        "若無法同時滿足，請保持清晰，不要變成另一種性別的聲線。"
        f"{HUMAN_VOICE_GUIDANCE}"
        f"{prosody_map(text)}"
        "以下情緒與演繹設定是控制指令，不是台詞，絕對不要朗讀或重複。"
        f"本次複合情緒：{emotion_line}；情緒強度：{intensity}。"
        f"演繹方式：{delivery}；語速節奏：{pace}；音高走向：{pitch}（{pitch_instruction(pitch)}）；"
        f"停頓策略：{pause}；收句方式：{ending}（{ending_instruction(ending)}）。"
        f"導演補充：{performance_note or '無'}。"
        "情緒要有層次、語句要清楚，避免過度誇張或破音；只完整朗讀一次台詞，不要重複任何字詞；"
        "保留句尾但不要拖長，台詞結束後立刻停止，尾部最多保留半秒。"
    )
    api_key, base_url = api_key_and_base_url()
    request_kwargs = {
        "api_key": api_key,
        "base_url": base_url,
        "model": "mimo-v2.5-tts-voiceclone",
        "context": context,
        # Keep the user dialogue isolated.  Control labels belong in context;
        # putting them into `text` makes TTS read the labels aloud and inflates
        # short lines into unexpectedly long takes.
        "text": text,
        "audio_format": "wav",
        "timeout": 180.0,
        "retries": 2,
        "voice": voice_data_url,
    }
    audio = request_audio(**request_kwargs)
    max_duration = duration_limit(text)
    generated_duration = wav_duration(audio)
    original_duration = generated_duration
    if generated_duration > max_duration * 1.25:
        # Very short lines can make a voice model loop.  Ask once more with a
        # hard one-pass instruction before falling back to deterministic trim.
        retry_kwargs = dict(request_kwargs)
        retry_kwargs["context"] = (
            context
            + f"這是短台詞，請只完整朗讀一次，預計不超過約 {max_duration:.0f} 秒。"
            "不要重複任何字詞，不要加入台詞之外的內容；說完最後一字後立刻停止，尾部最多保留半秒。"
        )
        retry_audio = request_audio(**retry_kwargs)
        if wav_duration(retry_audio) < generated_duration:
            audio = retry_audio
    selected_duration = wav_duration(audio)
    audio, duration_seconds = trim_wav(audio, max_duration)
    duration_limited = duration_seconds + 0.05 < selected_duration
    generation_id = now_id("take", seed_id, audio + text.encode("utf-8"))
    generation_file = f"{generation_id}.wav"
    GENERATIONS.mkdir(parents=True, exist_ok=True)
    atomic_write(GENERATIONS / generation_file, audio)
    duration_seconds = round(duration_seconds, 3)
    manifest_path = GENERATIONS / "manifest.json"
    manifest = load_json(manifest_path, {"schemaVersion": 1, "samples": []})
    if not isinstance(manifest, dict):
        manifest = {"schemaVersion": 1, "samples": []}
    manifest.setdefault("samples", [])
    manifest["samples"].append({
        "candidateId": generation_id,
        "characterId": record["name"],
        "displayName": record["name"],
        "voiceDisplay": record["name"],
        "gender": gender,
        "label": "、".join(emotions) or "平靜",
        "tags": ["聲音種子", *emotions, delivery, pace],
        "file": generation_file,
        "text": text,
        "voiceDescription": context,
        "seedId": seed_id,
        "seedSha256": record.get("referenceSha256"),
        "model": "mimo-v2.5-tts-voiceclone",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(audio).hexdigest(),
        "durationSeconds": duration_seconds,
        "originalDurationSeconds": round(original_duration, 3),
        "durationLimited": duration_limited,
        "intensity": intensity,
        "delivery": delivery,
        "pace": pace,
        "pitch": pitch,
        "pause": pause,
        "ending": ending,
        "performanceNote": performance_note,
    })
    manifest.update({
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "provider": "xiaomi_mimo",
        "model": "mimo-v2.5-tts-voiceclone",
        "galleryTitle": "聲音種子生成紀錄",
        "gallerySubtitle": "每一筆都保存聲音種子 hash 與複合情緒指令，方便追溯與重生。",
        "candidateCount": len(manifest["samples"]),
        "generatedCount": len(manifest["samples"]),
    })
    atomic_write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    write_generation_index(manifest)
    refresh_dashboard()
    return {
        "id": generation_id,
        "url": f"/voice_generations/{urllib.parse.quote(generation_file)}",
        "seedId": seed_id,
        "seedSha256": record.get("referenceSha256"),
        "gender": gender,
        "emotions": emotions,
        "intensity": intensity,
        "delivery": delivery,
        "pace": pace,
        "pitch": pitch,
        "pause": pause,
        "ending": ending,
        "durationSeconds": duration_seconds,
        "durationLimited": duration_limited,
        "model": "mimo-v2.5-tts-voiceclone",
    }


def write_generation_index(manifest: dict[str, Any]) -> None:
    cards = []
    for sample in manifest.get("samples", []):
        tags = " ".join(f"<span>{html.escape(str(tag))}</span>" for tag in sample.get("tags", []))
        cards.append(
            f"<article><h2>{html.escape(str(sample.get('label', '語音生成')))}</h2>"
            f"<div class='tags'>{tags}</div><audio controls preload='none' src='{html.escape(str(sample.get('file', '')))}'></audio>"
            f"<p>{html.escape(str(sample.get('text', '')))}</p><small>seed hash：{html.escape(str(sample.get('seedSha256', ''))[:16])}</small></article>"
        )
    page = "<!doctype html><html lang='zh-Hant'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>聲音種子生成紀錄</title><style>body{margin:0;background:#211a28;color:#fff7ee;font-family:-apple-system,BlinkMacSystemFont,'PingFang TC',sans-serif}main{max-width:1100px;margin:auto;padding:34px 20px}article{background:#302439;border:1px solid #72566a;border-radius:18px;padding:17px;margin:14px 0}.tags span{display:inline-block;background:#9f695d;border-radius:999px;padding:4px 8px;margin:3px;font-size:12px}audio{width:100%;margin:12px 0}p{white-space:pre-wrap;line-height:1.7;color:#dfccc7}a{color:#f2b89c}</style><main><p><a href='../index.html'>← 返回 Voice Seed Studio</a></p><h1>聲音種子生成紀錄</h1>" + "".join(cards) + "</main></html>"
    atomic_write(GENERATIONS / "index.html", page)


def refresh_dashboard() -> None:
    """Refresh the static homepage so a reload also shows the newest takes."""
    try:
        from build_test_dashboard import atomic_write as dashboard_write
        from build_test_dashboard import collect_tests, render_dashboard

        dashboard_write(OUTPUTS / "index.html", render_dashboard(collect_tests(OUTPUTS), outputs_root=OUTPUTS))
    except (ImportError, OSError, TypeError, ValueError) as exc:
        # The API result is already durable; a dashboard refresh must not turn
        # a successful generation into a failed request.
        sys.stderr.write(f"[studio] dashboard refresh skipped: {exc}\n")


class StudioHandler(SimpleHTTPRequestHandler):
    server_version = "VoiceSeedStudio/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("[studio] " + (format % args) + "\n")

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("請求大小無效") from exc
        if length <= 0 or length > MAX_UPLOAD_BYTES * 1.5:
            raise ValueError("請求大小超過限制")
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("請求格式必須是 JSON 物件")
        return data

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            self.send_json(200, {"ok": True, "service": "voice-seed-studio", "models": ["mimo-v2.5-tts-voicedesign", "mimo-v2.5-tts-voiceclone"]})
            return
        if path == "/api/seeds":
            self.send_json(200, {"seeds": seed_records()})
            return
        try:
            super().do_GET()
        except (BrokenPipeError, ConnectionResetError):
            # Browsers can stop an audio preview when the user switches pages;
            # the client disconnect is normal and should not pollute the log.
            return

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        try:
            payload = self.read_json()
            if parsed.path == "/api/seeds":
                kind = str(payload.get("kind", "text_design"))
                record = create_audio_seed(payload) if kind == "audio_clone" else create_text_seed(payload)
                self.send_json(201, {"ok": True, "seed": record})
                return
            if parsed.path == "/api/generate":
                result = generate_from_seed(payload)
                self.send_json(201, {"ok": True, "generation": result})
                return
            self.send_json(404, {"ok": False, "error": "Not found"})
        except (ValueError, RuntimeError, MimoRequestError, OSError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "error": str(exc)[:1000]})


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    SEEDS.mkdir(parents=True, exist_ok=True)
    GENERATIONS.mkdir(parents=True, exist_ok=True)
    existing_manifest = load_json(GENERATIONS / "manifest.json", None)
    if isinstance(existing_manifest, dict):
        changed = False
        for sample in existing_manifest.get("samples", []):
            if "voiceDisplay" not in sample and sample.get("displayName"):
                sample["voiceDisplay"] = sample.get("displayName")
                changed = True
            if "gender" not in sample:
                seed_record = load_json(SEEDS / safe_slug(str(sample.get("seedId", ""))) / "seed.json", {})
                sample["gender"] = normalize_gender(seed_record.get("gender")) if isinstance(seed_record, dict) else "不指定"
                changed = True
            if "durationSeconds" in sample:
                continue
            audio_path = GENERATIONS / str(sample.get("file", ""))
            if not audio_path.exists():
                continue
            try:
                with wave.open(str(audio_path), "rb") as stream:
                    sample["durationSeconds"] = round(stream.getnframes() / stream.getframerate(), 3) if stream.getframerate() else 0.0
                    changed = True
            except (OSError, wave.Error):
                continue
        if changed:
            atomic_write(GENERATIONS / "manifest.json", json.dumps(existing_manifest, ensure_ascii=False, indent=2) + "\n")
        write_generation_index(existing_manifest)
    handler = lambda *args, **kwargs: StudioHandler(*args, directory=str(OUTPUTS), **kwargs)
    server = HTTPServer((host, port), handler)
    print(f"Voice Seed Studio: http://{host}:{port}/index.html", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nVoice Seed Studio stopped.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server(
        host=sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1",
        port=int(sys.argv[2]) if len(sys.argv) > 2 else 8765,
    )
