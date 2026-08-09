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
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from cinema_templates import get_cinema_template
from dialogue_scene_templates import get_dialogue_scene
from generate_tts_catalog import load_local_env
from paths import resolve_workspace_root
from providers.mimo import DEFAULT_BASE_URL, MimoRequestError, request_audio
import seed_asset_system as asset_system


ROOT = resolve_workspace_root()
OUTPUTS = ROOT / "outputs"
SEEDS = OUTPUTS / "voice_seeds"
GENERATIONS = OUTPUTS / "voice_generations"
DIALOGUE_SCENES = OUTPUTS / "dialogue_scenes"
DEFAULT_PORT = 8888
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
SAFE_ID = re.compile(r"[^a-zA-Z0-9_-]+")
EMOTIONS = ["怅然", "欣慰", "得意", "無奈", "愧疚", "釋然", "嫉妒", "厭倦", "忐忑", "動情"]
GENDERS = {"女性", "男性", "中性／不指定", "不指定"}
DELIVERIES = {"電影對白", "古裝台詞", "內心獨白", "旁白敘事", "低語耳語", "舞台宣告", "質問逼問", "安撫哄勸"}
PACES = {"慢速", "標準", "快速", "忽快忽慢"}
PITCHES = {"自然", "自然起伏", "偏低沉", "偏明亮", "先低後高", "先高後低"}
PAUSES = {"自然停頓", "短停頓", "長停頓", "句尾留白", "斷續哽咽"}
ENDINGS = {"完整收句", "尾音放輕", "欲言又止", "情緒停住但不截斷"}
CINEMA_SHOTS = {"電影特寫", "電影近景", "電視劇近景", "電視劇中景"}
CINEMA_TAKES = {"克制真實", "生活流", "節奏推進", "職人寫實", "古裝含蓄", "史詩克制", "自然青春", "喜劇節拍", "動作壓迫", "年代含蓄"}
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


def cinema_performance(payload: dict[str, Any], text: str) -> tuple[str, str, dict[str, Any] | None]:
    """Build a playable screen-acting brief from a trusted original template.

    Rich acting directions stay in the user-role context.  Only MiMo-supported
    inline audio tags enter the assistant-role content, and only while the
    displayed dialogue is still byte-for-byte the curated original.  As soon
    as a user edits the line, the edited dialogue is sent cleanly without stale
    tags or hidden template text.
    """
    template = get_cinema_template(str(payload.get("cinemaTemplateId", "")))
    if not template:
        return "", text, None
    requested_shot = str(payload.get("shotScale", "")).strip()
    requested_take = str(payload.get("takeStyle", "")).strip()
    shot_scale = requested_shot if requested_shot in CINEMA_SHOTS else str(template["shotScale"])
    take_style = requested_take if requested_take in CINEMA_TAKES else str(template["takeStyle"])
    circumstance = str(template["circumstance"]).rstrip("。；; ")
    relationship = str(template["relationship"]).rstrip("。；; ")
    objective = str(template["objective"]).rstrip("。；; ")
    obstacle = str(template["obstacle"]).rstrip("。；; ")
    subtext = str(template["subtext"]).rstrip("。；; ")
    beats = template.get("beats", [])
    beat_score = "；".join(
        f"第{index}拍「{str(beat[0])[:30]}」：{str(beat[1])[:140]}"
        for index, beat in enumerate(beats[:4], start=1)
        if isinstance(beat, (list, tuple)) and len(beat) >= 2
    )
    direction = (
        "影視配音模式：把這段當成鏡頭前正在發生的戲，不是朗誦、廣告、預告片或情緒展示。"
        f"作品類型：{template['format']}／{template['genre']}；鏡頭距離：{shot_scale}；表演版本：{take_style}。"
        f"既定情境：{circumstance}；人物關係：{relationship}。"
        f"人物此刻可執行的目的：{objective}；阻力：{obstacle}。"
        f"潛台詞：{subtext}。潛台詞只能透過思考、呼吸、重音與停頓被感覺到，不能另加台詞說明。"
        f"表演節拍：{beat_score}。"
        "表演規則：每句先有念頭再出聲；接話要像正在聽對手，而不是預先背稿；近景縮小音量與動作，"
        "情緒峰值只放在真正轉折處。允許自然吸氣、猶豫和不完全對稱的節奏，但咬字必須清楚。"
        "不要把人物目的、阻力、潛台詞、節拍或括號標籤念出來；不要自行添加旁白、角色名或解釋。"
    )
    assistant_text = str(template.get("taggedText", text)) if text == str(template.get("text", "")) else text
    metadata = {
        "templateId": template["id"],
        "title": template["title"],
        "format": template["format"],
        "genre": template["genre"],
        "shotScale": shot_scale,
        "takeStyle": take_style,
        "usedInlineTags": assistant_text != text,
    }
    return direction, assistant_text, metadata


def wav_duration(audio: bytes) -> float:
    """Read a WAV duration without writing a temporary file."""
    with wave.open(io.BytesIO(audio), "rb") as stream:
        return stream.getnframes() / stream.getframerate() if stream.getframerate() else 0.0


def duration_limit(text: str) -> float:
    """Keep generated speech proportional to the amount of written dialogue."""
    spoken_chars = len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", text))
    return max(8.0, min(52.0, 4.0 + spoken_chars * 0.65))


def load_seed_reference(
    seed_id: str,
    anchor_id: str = "",
    performance_tags: list[str] | None = None,
) -> tuple[dict[str, Any], str, str]:
    """Load one locked seed and return its record, gender and data URL."""
    seed_id = str(seed_id).strip()
    record, anchor, reference_path = asset_system.resolve_anchor(
        OUTPUTS, seed_id, anchor_id=anchor_id, performance_tags=performance_tags
    )
    reference_audio = reference_path.read_bytes()
    mime = str(anchor.get("mime", record.get("referenceMime", "audio/wav")))
    data_url = f"data:{mime};base64,{base64.b64encode(reference_audio).decode('ascii')}"
    selected_record = dict(record)
    selected_record["selectedAnchorId"] = anchor.get("id")
    selected_record["selectedAnchorLabel"] = anchor.get("label")
    selected_record["selectedAnchorSha256"] = anchor.get("sha256")
    return selected_record, normalize_gender(record.get("gender")), data_url


def synthesize_locked_take(
    *, seed_id: str, text: str, assistant_text: str, context: str,
    anchor_id: str = "", performance_tags: list[str] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Generate one voice-locked WAV with retry and deterministic length guards."""
    record, gender, voice_data_url = load_seed_reference(seed_id, anchor_id, performance_tags)
    voice_lock = (
        "這是一個已鎖定的聲音種子。保持參考音檔的音色身份、年齡、性別、共鳴位置、口音與說話習慣，"
        "不得因角色、情緒或場景重新設計聲線，只改變本次表演。"
        f"{gender_instruction(gender)} 若參考音檔與性別設定衝突，以性別設定優先。"
    )
    api_key, base_url = api_key_and_base_url()
    request_kwargs = {
        "api_key": api_key,
        "base_url": base_url,
        "model": "mimo-v2.5-tts-voiceclone",
        "context": voice_lock + context,
        "text": assistant_text,
        "audio_format": "wav",
        "timeout": 180.0,
        "retries": 2,
        "voice": voice_data_url,
    }
    audio = request_audio(**request_kwargs)
    max_duration = duration_limit(text)
    original_duration = wav_duration(audio)
    if original_duration > max_duration * 1.25:
        retry_kwargs = dict(request_kwargs)
        retry_kwargs["context"] = (
            request_kwargs["context"]
            + f"這句預計不超過約 {max_duration:.0f} 秒；只說一次，不得重複、續寫或補充。"
            "最後一字完成後立刻停止，尾部最多半秒。"
        )
        retry_audio = request_audio(**retry_kwargs)
        if wav_duration(retry_audio) < original_duration:
            audio = retry_audio
    selected_duration = wav_duration(audio)
    audio, duration_seconds = trim_wav(audio, max_duration)
    return audio, {
        "record": record,
        "gender": gender,
        "durationSeconds": round(duration_seconds, 3),
        "originalDurationSeconds": round(original_duration, 3),
        "durationLimited": duration_seconds + 0.05 < selected_duration,
    }


def dialogue_turn_context(scene: dict[str, Any], turn_index: int) -> tuple[str, str]:
    """Build a turn-specific acting brief and trusted assistant text."""
    turns = scene.get("turns", [])
    if turn_index < 0 or turn_index >= len(turns):
        raise ValueError("對白回合不存在")
    turn = turns[turn_index]
    role_key = str(turn.get("role", ""))
    role = scene.get("roles", {}).get(role_key)
    if not isinstance(role, dict):
        raise ValueError("場景角色設定不完整")
    previous = turns[turn_index - 1] if turn_index else None
    previous_cue = str(previous.get("text", "")) if isinstance(previous, dict) else "場景開始前已經看見對方"
    text = str(turn.get("text", "")).strip()
    assistant_text = str(turn.get("taggedText", text)).strip() or text
    context = (
        "雙人影視對手戲模式：這是一個逐句錄製的 take，但人物必須像正在同一空間聽見對手後才開口；"
        "不是朗誦、配音展示、預告旁白或獨立情緒樣本。"
        f"場景：{scene['format']}／{scene['genre']}《{scene['title']}》；情境：{scene['circumstance']}；"
        f"關係：{scene['relationship']}；鏡頭：{scene['shotScale']}；表演版本：{scene['takeStyle']}。"
        f"你只扮演角色 {role['name']}；人物目的：{role['objective']}；潛台詞：{role['subtext']}。"
        f"上一個聽覺提示：{previous_cue}；接話反應：{turn.get('listen', '先聽再說')}。"
        f"本句情緒：{turn.get('emotion', '自然')}；本句導演要求：{turn.get('direction', '自然接話')}。"
        f"{HUMAN_VOICE_GUIDANCE}{prosody_map(text)}"
        "每句先有接收到對方的反應，再開口；不要補演對手台詞、角色名、情境、目的、潛台詞、情緒或導演要求。"
        "括號與方括號若出現在 assistant 訊息中，只是官方表演／音訊標籤，不得念出。"
        "只演本句一次，不重複、不續寫、不加前言或尾聲；最後一字完成後停止，尾部最多半秒。"
    )
    return context, assistant_text


def stitch_wav_lines(lines: list[bytes], pauses: list[float]) -> tuple[bytes, float]:
    """Join compatible PCM WAV takes and insert exact silence between turns."""
    if not lines or len(lines) != len(pauses):
        raise ValueError("場景音訊或停頓資料不完整")
    params = None
    joined = bytearray()
    for audio, pause_seconds in zip(lines, pauses):
        with wave.open(io.BytesIO(audio), "rb") as source:
            current = source.getparams()
            frames = source.readframes(source.getnframes())
        signature = (current.nchannels, current.sampwidth, current.framerate, current.comptype)
        if params is None:
            params = current
            expected = signature
        elif signature != expected:
            raise ValueError("各句 WAV 格式不同，無法安全合併；請重新生成本場景")
        joined.extend(frames)
        silence_frames = max(0, int(current.framerate * max(0.0, pause_seconds)))
        joined.extend(b"\x00" * silence_frames * current.nchannels * current.sampwidth)
    assert params is not None
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setparams(params)
        target.writeframes(bytes(joined))
    frame_bytes = params.nchannels * params.sampwidth
    duration = len(joined) / frame_bytes / params.framerate
    return output.getvalue(), round(duration, 3)


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
    return asset_system.seed_summaries(OUTPUTS)


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
    asset_system.ensure_passport(OUTPUTS, seed_id)
    record["audioUrl"] = f"/voice_seeds/{urllib.parse.quote(seed_id)}/{urllib.parse.quote(reference_file)}"
    return record


def generate_from_seed(payload: dict[str, Any]) -> dict[str, Any]:
    performance_seed_id = str(payload.get("performanceSeedId", "")).strip()
    performance_seed = asset_system.get_performance_seed(OUTPUTS, performance_seed_id) if performance_seed_id else None
    if performance_seed_id and not performance_seed:
        raise ValueError("找不到指定表演種子")
    if performance_seed:
        payload = {**performance_seed, **payload}
    seed_id = str(payload.get("seedId", "")).strip()
    text = str(payload.get("text", "")).strip()
    emotions = [str(item).strip() for item in payload.get("emotions", []) if str(item).strip()]
    intensity = str(payload.get("intensity", "自然")).strip() or "自然"
    delivery = normalize_option(payload.get("delivery"), DELIVERIES, "電影對白")
    pace = normalize_option(payload.get("pace"), PACES, "標準")
    pitch = normalize_option(payload.get("pitch"), PITCHES, "自然")
    pause = normalize_option(payload.get("pause"), PAUSES, "自然停頓")
    ending = normalize_option(payload.get("ending"), ENDINGS, "完整收句")
    performance_note = str(payload.get("performanceNote") or (performance_seed or {}).get("note", "")).strip()[:500]
    if not seed_id or not text:
        raise ValueError("生成語音需要聲音種子與台詞")
    if len(text) > 8000:
        raise ValueError("單次台詞最多 8000 字")
    emotions = list(dict.fromkeys(emotions))[:5]
    anchor_id = str(payload.get("anchorId", "")).strip()
    anchor_modes = performance_seed.get("anchorModes", []) if performance_seed else []
    record, gender, voice_data_url = load_seed_reference(seed_id, anchor_id, anchor_modes)
    emotion_line = "、".join(emotions) if emotions else "平靜"
    cinema_direction, assistant_text, cinema_metadata = cinema_performance(payload, text)
    voice_lock = (
        "這是一個已鎖定的聲音種子。保持參考音檔的音色身份、年齡、性別、共鳴位置、口音與說話習慣，"
        "不要重新設計聲線，只改變本次表演。"
        f"{gender_instruction(gender)} 若參考音檔與性別設定衝突，以性別設定優先。"
    )
    if cinema_metadata:
        context = (
            f"{voice_lock}{cinema_direction}"
            f"整體情緒弧線：{emotion_line}；強度：{intensity}；語速：{pace}；"
            f"音高原則：{pitch_instruction(pitch)}；收句原則：{ending_instruction(ending)}。"
            f"導演補充：{(performance_note or '依模板節拍演出').rstrip('。；; ')}。"
            "只演一次，只說 assistant 訊息中的台詞；內嵌括號與方括號是官方表演／音訊標籤，不得念出。"
            "不重複任何字詞，不添加前言或尾聲；最後一字完成後停止，尾部最多半秒。"
        )
    else:
        context = (
            f"{voice_lock}{HUMAN_VOICE_GUIDANCE}{prosody_map(text)}"
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
        "text": assistant_text,
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
    _, selected_anchor, reference_path = asset_system.resolve_anchor(
        OUTPUTS, seed_id, anchor_id=str(record.get("selectedAnchorId", ""))
    )
    reference_signature = asset_system.audio_signature(reference_path)
    take_signature = asset_system.audio_signature(GENERATIONS / generation_file)
    acoustic_score = asset_system.acoustic_similarity(reference_signature, take_signature)
    gate_reasons: list[str] = []
    if duration_limited:
        gate_reasons.append("模型輸出曾超出長度護欄，建議人工試聽")
    if acoustic_score is not None and acoustic_score < 58:
        gate_reasons.append("聲學輪廓偏離 Active 錨點")
    quality_gate = {
        "status": "review" if gate_reasons else "pass",
        "acousticSimilarity": acoustic_score,
        "anchorId": selected_anchor.get("id"),
        "durationGuardTriggered": duration_limited,
        "reasons": gate_reasons or ["長度與聲學輪廓通過自動門禁"],
        "method": "local-signal-gate-v1",
    }
    manifest_path = GENERATIONS / "manifest.json"
    manifest = load_json(manifest_path, {"schemaVersion": 1, "samples": []})
    if not isinstance(manifest, dict):
        manifest = {"schemaVersion": 1, "samples": []}
    manifest.setdefault("samples", [])
    generation_tags = ["聲音種子", *emotions, delivery, pace]
    if cinema_metadata:
        generation_tags = ["影視配音", cinema_metadata["genre"], *emotions]
    manifest["samples"].append({
        "candidateId": generation_id,
        "characterId": record["name"],
        "displayName": record["name"],
        "voiceDisplay": record["name"],
        "gender": gender,
        "label": cinema_metadata["title"] if cinema_metadata else ("、".join(emotions) or "平靜"),
        "tags": generation_tags,
        "file": generation_file,
        "text": text,
        "voiceDescription": context,
        "seedId": seed_id,
        "seedSha256": record.get("referenceSha256"),
        "anchorId": record.get("selectedAnchorId"),
        "anchorSha256": record.get("selectedAnchorSha256"),
        "performanceSeedId": performance_seed_id or None,
        "performanceSeedName": performance_seed.get("name") if performance_seed else None,
        "qualityGate": quality_gate,
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
        "cinema": cinema_metadata,
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
    result = {
        "id": generation_id,
        "url": f"/voice_generations/{urllib.parse.quote(generation_file)}",
        "seedId": seed_id,
        "seedSha256": record.get("referenceSha256"),
        "anchorId": record.get("selectedAnchorId"),
        "anchorLabel": record.get("selectedAnchorLabel"),
        "performanceSeedId": performance_seed_id or None,
        "performanceSeedName": performance_seed.get("name") if performance_seed else None,
        "qualityGate": quality_gate,
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
    if cinema_metadata:
        result["cinema"] = cinema_metadata
    return result


def _dialogue_scene_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": manifest["id"],
        "templateId": manifest["templateId"],
        "title": manifest["title"],
        "format": manifest["format"],
        "genre": manifest["genre"],
        "createdAt": manifest["createdAt"],
        "updatedAt": manifest["updatedAt"],
        "durationSeconds": manifest["durationSeconds"],
        "lineCount": len(manifest.get("lines", [])),
        "sceneFile": f"{manifest['id']}/scene.wav",
        "roles": manifest.get("roles", {}),
    }


def update_dialogue_catalog(manifest: dict[str, Any]) -> None:
    catalog_path = DIALOGUE_SCENES / "manifest.json"
    catalog = load_json(catalog_path, {"schemaVersion": 1, "scenes": []})
    if not isinstance(catalog, dict):
        catalog = {"schemaVersion": 1, "scenes": []}
    scenes = [item for item in catalog.get("scenes", []) if isinstance(item, dict) and item.get("id") != manifest["id"]]
    scenes.append(_dialogue_scene_summary(manifest))
    scenes.sort(key=lambda item: str(item.get("updatedAt", "")), reverse=True)
    catalog.update({
        "schemaVersion": 1,
        "galleryTitle": "雙人對手戲",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sceneCount": len(scenes),
        "scenes": scenes,
    })
    atomic_write(catalog_path, json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")


def rebuild_dialogue_scene_audio(scene_dir: Path, manifest: dict[str, Any]) -> None:
    audio_lines: list[bytes] = []
    pauses: list[float] = []
    for line in manifest.get("lines", []):
        line_path = scene_dir / str(line.get("file", ""))
        if not line_path.exists():
            raise ValueError(f"場景缺少第 {int(line.get('index', 0)) + 1} 句音檔")
        audio_lines.append(line_path.read_bytes())
        pauses.append(float(line.get("pauseAfterSeconds", 0.0)))
    scene_audio, duration_seconds = stitch_wav_lines(audio_lines, pauses)
    atomic_write(scene_dir / "scene.wav", scene_audio)
    manifest["durationSeconds"] = duration_seconds
    manifest["sha256"] = hashlib.sha256(scene_audio).hexdigest()
    manifest["updatedAt"] = datetime.now(timezone.utc).isoformat()
    atomic_write(scene_dir / "scene.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    update_dialogue_catalog(manifest)


def generate_dialogue_scene(payload: dict[str, Any]) -> dict[str, Any]:
    """Generate all turns of one two-character scene and a stitched master."""
    template_id = str(payload.get("sceneTemplateId", "")).strip()
    scene = get_dialogue_scene(template_id)
    if not scene:
        raise ValueError("找不到指定雙人場景")
    role_seeds = payload.get("roleSeeds", {})
    if not isinstance(role_seeds, dict):
        raise ValueError("請為 A、B 角色指定聲音種子")
    cast: dict[str, str] = {}
    for role_key in scene.get("roles", {}):
        seed_id = str(role_seeds.get(role_key, "")).strip()
        if not seed_id:
            raise ValueError(f"角色 {role_key} 尚未指定聲音種子")
        load_seed_reference(seed_id)
        cast[role_key] = seed_id
    if len(set(cast.values())) != len(cast):
        raise ValueError("雙人對手戲請為 A、B 選擇不同聲音種子")
    try:
        pause_scale = float(payload.get("pauseScale", 1.0))
    except (TypeError, ValueError) as exc:
        raise ValueError("對手戲停頓倍率無效") from exc
    pause_scale = min(1.75, max(0.5, pause_scale))
    identity = json.dumps({"template": template_id, "cast": cast, "pause": pause_scale}, sort_keys=True).encode("utf-8")
    scene_id = now_id("scene", template_id, identity + os.urandom(8))
    scene_dir = DIALOGUE_SCENES / scene_id
    lines_dir = scene_dir / "lines"
    lines_dir.mkdir(parents=True, exist_ok=False)
    created_at = datetime.now(timezone.utc).isoformat()
    role_manifest: dict[str, Any] = {}
    for role_key, role in scene["roles"].items():
        seed_record, seed_gender, _ = load_seed_reference(cast[role_key])
        role_manifest[role_key] = {
            "name": role["name"],
            "suggestedGender": role.get("gender", "不指定"),
            "seedId": cast[role_key],
            "seedName": seed_record.get("name", cast[role_key]),
            "seedGender": seed_gender,
            "seedSha256": seed_record.get("referenceSha256"),
        }
    manifest: dict[str, Any] = {
        "schemaVersion": 1,
        "id": scene_id,
        "templateId": template_id,
        "title": scene["title"],
        "format": scene["format"],
        "genre": scene["genre"],
        "hook": scene["hook"],
        "circumstance": scene["circumstance"],
        "relationship": scene["relationship"],
        "shotScale": scene["shotScale"],
        "takeStyle": scene["takeStyle"],
        "pauseScale": pause_scale,
        "roles": role_manifest,
        "model": "mimo-v2.5-tts-voiceclone",
        "createdAt": created_at,
        "updatedAt": created_at,
        "lines": [],
    }
    try:
        for index, turn in enumerate(scene["turns"]):
            role_key = str(turn["role"])
            text = str(turn["text"]).strip()
            context, assistant_text = dialogue_turn_context(scene, index)
            audio, take = synthesize_locked_take(
                seed_id=cast[role_key], text=text, assistant_text=assistant_text, context=context
            )
            filename = f"line_{index + 1:02d}_{role_key}.wav"
            relative_file = f"lines/{filename}"
            atomic_write(lines_dir / filename, audio)
            manifest["lines"].append({
                "index": index,
                "role": role_key,
                "roleName": scene["roles"][role_key]["name"],
                "seedId": cast[role_key],
                "seedName": take["record"].get("name", cast[role_key]),
                "seedSha256": take["record"].get("referenceSha256"),
                "gender": take["gender"],
                "text": text,
                "emotion": turn.get("emotion", "自然"),
                "direction": turn.get("direction", "自然接話"),
                "listen": turn.get("listen", "先聽再說"),
                "pauseAfterSeconds": round(float(turn.get("pauseAfter", 0.6)) * pause_scale, 3),
                "file": relative_file,
                "durationSeconds": take["durationSeconds"],
                "originalDurationSeconds": take["originalDurationSeconds"],
                "durationLimited": take["durationLimited"],
                "sha256": hashlib.sha256(audio).hexdigest(),
                "createdAt": datetime.now(timezone.utc).isoformat(),
            })
        rebuild_dialogue_scene_audio(scene_dir, manifest)
    except Exception:
        # Keep already generated line takes for diagnosis and recovery; mark the
        # partial scene explicitly instead of silently presenting it as ready.
        manifest["status"] = "partial"
        manifest["updatedAt"] = datetime.now(timezone.utc).isoformat()
        atomic_write(scene_dir / "scene.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        raise
    manifest["status"] = "ready"
    atomic_write(scene_dir / "scene.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    update_dialogue_catalog(manifest)
    refresh_dashboard()
    return dialogue_scene_result(manifest)


def regenerate_dialogue_line(payload: dict[str, Any]) -> dict[str, Any]:
    """Replace one line take and rebuild the complete scene master."""
    scene_id = str(payload.get("sceneId", "")).strip()
    try:
        line_index = int(payload.get("lineIndex", -1))
    except (TypeError, ValueError) as exc:
        raise ValueError("重生句序無效") from exc
    scene_dir = DIALOGUE_SCENES / safe_slug(scene_id)
    manifest = load_json(scene_dir / "scene.json", None)
    if not isinstance(manifest, dict) or manifest.get("id") != scene_id:
        raise ValueError("找不到指定雙人場景成品")
    scene = get_dialogue_scene(str(manifest.get("templateId", "")))
    if not scene or line_index < 0 or line_index >= len(manifest.get("lines", [])):
        raise ValueError("找不到指定對白回合")
    line = manifest["lines"][line_index]
    role_key = str(line["role"])
    seed_id = str(payload.get("seedId", "")).strip() or str(line["seedId"])
    context, assistant_text = dialogue_turn_context(scene, line_index)
    text = str(line["text"])
    audio, take = synthesize_locked_take(seed_id=seed_id, text=text, assistant_text=assistant_text, context=context)
    line_path = scene_dir / str(line["file"])
    atomic_write(line_path, audio)
    line.update({
        "seedId": seed_id,
        "seedName": take["record"].get("name", seed_id),
        "seedSha256": take["record"].get("referenceSha256"),
        "gender": take["gender"],
        "durationSeconds": take["durationSeconds"],
        "originalDurationSeconds": take["originalDurationSeconds"],
        "durationLimited": take["durationLimited"],
        "sha256": hashlib.sha256(audio).hexdigest(),
        "createdAt": datetime.now(timezone.utc).isoformat(),
    })
    rebuild_dialogue_scene_audio(scene_dir, manifest)
    refresh_dashboard()
    return dialogue_scene_result(manifest)


def dialogue_scene_result(manifest: dict[str, Any]) -> dict[str, Any]:
    scene_id = str(manifest["id"])
    quoted_id = urllib.parse.quote(scene_id)
    return {
        "id": scene_id,
        "templateId": manifest["templateId"],
        "title": manifest["title"],
        "format": manifest["format"],
        "genre": manifest["genre"],
        "url": f"/dialogue_scenes/{quoted_id}/scene.wav",
        "manifestUrl": f"/dialogue_scenes/{quoted_id}/scene.json",
        "durationSeconds": manifest.get("durationSeconds", 0.0),
        "lineCount": len(manifest.get("lines", [])),
        "roles": manifest.get("roles", {}),
        "lines": [
            {
                **{key: line.get(key) for key in ("index", "role", "roleName", "seedId", "seedName", "gender", "text", "emotion", "durationSeconds", "durationLimited")},
                "url": f"/dialogue_scenes/{quoted_id}/{urllib.parse.quote(str(line.get('file', '')))}",
            }
            for line in manifest.get("lines", [])
        ],
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
        if path == "/api/studio/overview":
            self.send_json(200, asset_system.studio_overview(OUTPUTS))
            return
        if path == "/api/performance-seeds":
            self.send_json(200, {"items": asset_system.performance_seeds(OUTPUTS)})
            return
        if path == "/api/continuity-projects":
            self.send_json(200, {"items": asset_system.continuity_projects(OUTPUTS)})
            return
        if path == "/api/dialogue-scenes":
            catalog = load_json(DIALOGUE_SCENES / "manifest.json", {"schemaVersion": 1, "scenes": []})
            self.send_json(200, catalog if isinstance(catalog, dict) else {"schemaVersion": 1, "scenes": []})
            return
        seed_match = re.fullmatch(r"/api/seeds/([^/]+)", path)
        if seed_match:
            seed_id = urllib.parse.unquote(seed_match.group(1))
            self.send_json(200, {"asset": asset_system.seed_asset(OUTPUTS, seed_id)})
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
            if parsed.path == "/api/performance-seeds":
                result = asset_system.create_performance_seed(OUTPUTS, payload)
                self.send_json(201, {"ok": True, "performance": result})
                return
            if parsed.path == "/api/casting/recommend":
                self.send_json(200, {"ok": True, "recommendations": asset_system.recommend_cast(OUTPUTS, payload)})
                return
            if parsed.path == "/api/continuity-projects":
                result = asset_system.save_continuity_project(OUTPUTS, payload)
                self.send_json(201, {"ok": True, "project": result})
                return
            if parsed.path == "/api/dialogue-scenes":
                result = generate_dialogue_scene(payload)
                self.send_json(201, {"ok": True, "scene": result})
                return
            if parsed.path == "/api/dialogue-scenes/regenerate-line":
                result = regenerate_dialogue_line(payload)
                self.send_json(200, {"ok": True, "scene": result})
                return
            seed_action = re.fullmatch(r"/api/seeds/([^/]+)/(anchors|versions|activate-version|certify|export)", parsed.path)
            if seed_action:
                seed_id = urllib.parse.unquote(seed_action.group(1))
                action = seed_action.group(2)
                if action == "anchors":
                    mime, audio = decode_data_url(str(payload.get("dataUrl", "")))
                    result = asset_system.add_anchor(OUTPUTS, seed_id, payload, mime, audio, mime_extension(mime))
                    self.send_json(201, {"ok": True, "asset": result})
                    return
                if action == "versions":
                    result = asset_system.create_version(OUTPUTS, seed_id, payload)
                    self.send_json(201, {"ok": True, "asset": result})
                    return
                if action == "activate-version":
                    result = asset_system.activate_version(OUTPUTS, seed_id, str(payload.get("versionId", "")))
                    self.send_json(200, {"ok": True, "asset": result})
                    return
                if action == "certify":
                    stress_results = []
                    if str(payload.get("mode", "offline")) == "full":
                        for test in (
                            {"performanceSeedId": "perf_intimate_reality", "text": "我知道。你先別急，讓我把這句話說完。"},
                            {"performanceSeedId": "perf_held_tears", "text": "我沒有怪你……只是那天，我真的等了很久。"},
                            {"performanceSeedId": "perf_authority_cold", "text": "把門關上。從現在起，每一個答案都要說清楚。"},
                            {"performanceSeedId": "perf_comedy_bounce", "text": "等等，所以你忙了整晚，只是忘了按開始？"},
                        ):
                            stress_results.append(generate_from_seed({"seedId": seed_id, **test}))
                    result = asset_system.certify_seed(OUTPUTS, seed_id)
                    self.send_json(201, {"ok": True, "certification": result, "stressResults": stress_results})
                    return
                result = asset_system.export_voicepack(OUTPUTS, seed_id)
                self.send_json(201, {"ok": True, "voicepack": result})
                return
            self.send_json(404, {"ok": False, "error": "Not found"})
        except (ValueError, RuntimeError, MimoRequestError, OSError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "error": str(exc)[:1000]})


def run_server(host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    SEEDS.mkdir(parents=True, exist_ok=True)
    GENERATIONS.mkdir(parents=True, exist_ok=True)
    DIALOGUE_SCENES.mkdir(parents=True, exist_ok=True)
    asset_system.ensure_layout(OUTPUTS)
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
    server = ThreadingHTTPServer((host, port), handler)
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
        port=int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT,
    )
