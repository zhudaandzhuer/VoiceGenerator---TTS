#!/usr/bin/env python3
"""Audio-only ancient-recitation mixer with original local BGM beds.

The mixer preserves a dry locked-seed take, derives a lightly spatialized voice,
ducks music from the actual speech signal, and masters WAV/MP3 deliverables.
It never modifies the source voice seed and never renders video.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import shutil
import struct
import subprocess
import tempfile
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ancient_audio_templates import BGM_PRESETS, get_bgm_preset, get_room_preset


MUSIC_LEVELS = {"voice-first": 0.16, "balanced": 0.22, "cinematic": 0.29}
ROOM_FILTERS = {
    "dry": "anull",
    "warm-study": "aecho=0.82:0.88:28|53:0.055|0.025",
    "stone-pavilion": "aecho=0.80:0.86:34|71:0.075|0.035",
    "great-hall": "aecho=0.78:0.84:38|83|137:0.085|0.045|0.022",
    "open-air": "aecho=0.86:0.90:47:0.025",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run(command: list[str], *, timeout: float = 240.0) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError("找不到 ffmpeg／ffprobe；請先安裝 FFmpeg") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or "未知錯誤").strip().splitlines()
        raise RuntimeError("音訊處理失敗：" + (detail[-1] if detail else "FFmpeg error"))
    return result


def audio_probe(path: Path) -> dict[str, Any]:
    result = run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_name,sample_rate,channels", "-of", "json", str(path),
    ], timeout=30.0)
    payload = json.loads(result.stdout or "{}")
    streams = payload.get("streams", [])
    stream = streams[0] if streams else {}
    duration = float((payload.get("format") or {}).get("duration") or 0.0)
    if duration <= 0:
        raise ValueError(f"音檔沒有有效時長：{path.name}")
    return {
        "durationSeconds": round(duration, 3),
        "codec": stream.get("codec_name"),
        "sampleRate": int(stream.get("sample_rate") or 0),
        "channels": int(stream.get("channels") or 0),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def loudness_probe(path: Path) -> dict[str, float | None]:
    result = run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-",
    ], timeout=60.0)
    text = result.stderr
    import re
    integrated = re.findall(r"I:\s*(-?[0-9.]+) LUFS", text)
    range_values = re.findall(r"LRA:\s*([0-9.]+) LU", text)
    peaks = re.findall(r"Peak:\s*(-?[0-9.]+) dBFS", text)
    return {
        "integratedLufs": float(integrated[-1]) if integrated else None,
        "loudnessRangeLu": float(range_values[-1]) if range_values else None,
        "truePeakDbfs": float(peaks[-1]) if peaks else None,
    }


def _music_notes(style: str) -> tuple[int, list[int], float, float]:
    return {
        "mountain": (50, [0, 7, 12, 16, 19, 24, 19, 12], 0.42, 0.10),
        "moon": (47, [0, 4, 7, 11, 14, 11, 7, 4], 0.50, 0.13),
        "frontier": (38, [0, 7, 12, 14, 19, 14, 12, 7], 0.34, 0.16),
        "palace": (41, [0, 1, 7, 8, 13, 8, 7, 1], 0.58, 0.11),
    }[style]


def synthesize_original_bgm(target: Path, style: str, duration: float = 36.0) -> None:
    """Create a restrained, loopable pentatonic bed and encode it as MP3."""
    if style not in {"mountain", "moon", "frontier", "palace"}:
        raise ValueError("未知的本機配樂類型")
    sample_rate = 24000
    root_midi, intervals, step_seconds, pluck_level = _music_notes(style)
    frame_count = int(sample_rate * duration)
    rng = random.Random(f"voice-seed-audio-scene::{style}::v1")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="voice-seed-bgm-") as temporary:
        raw_path = Path(temporary) / "source.wav"
        with wave.open(str(raw_path), "wb") as output:
            output.setnchannels(2)
            output.setsampwidth(2)
            output.setframerate(sample_rate)
            block = bytearray()
            for index in range(frame_count):
                t = index / sample_rate
                step = int(t / step_seconds)
                local = t - step * step_seconds
                interval = intervals[step % len(intervals)]
                frequency = 440.0 * (2.0 ** ((root_midi + interval - 69) / 12.0))
                # A breath-like drone supplies continuity; sparse plucks carry melody.
                drone = 0.045 * math.sin(2 * math.pi * (frequency / 4) * t)
                drone += 0.018 * math.sin(2 * math.pi * (frequency / 2) * t + 0.7)
                envelope = math.exp(-local * (5.2 if style != "moon" else 4.0))
                pluck = pluck_level * envelope * (
                    math.sin(2 * math.pi * frequency * local)
                    + 0.36 * math.sin(2 * math.pi * frequency * 2.01 * local)
                    + 0.14 * math.sin(2 * math.pi * frequency * 3.98 * local)
                )
                texture = 0.004 * rng.uniform(-1, 1) * (0.3 + 0.7 * math.sin(math.pi * (t % 5.0) / 5.0) ** 2)
                drum = 0.0
                if style == "frontier":
                    beat = t % 1.58
                    drum = 0.22 * math.exp(-beat * 11) * math.sin(2 * math.pi * (55 - 12 * beat) * beat)
                elif style == "palace" and step % 8 == 6:
                    drum = 0.055 * math.exp(-local * 8) * math.sin(2 * math.pi * 740 * local)
                pan = 0.22 * math.sin(step * 1.7)
                left = max(-0.95, min(0.95, drone + pluck * (1 - pan) + drum + texture))
                right = max(-0.95, min(0.95, drone + pluck * (1 + pan) + drum - texture))
                block.extend(struct.pack("<hh", int(left * 32767), int(right * 32767)))
                if len(block) >= 65536:
                    output.writeframesraw(block)
                    block.clear()
            if block:
                output.writeframesraw(block)
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw_path),
            "-af", "highpass=f=35,lowpass=f=9000,acompressor=threshold=0.2:ratio=2:attack=30:release=300,loudnorm=I=-25:TP=-3:LRA=10",
            "-c:a", "libmp3lame", "-b:a", "160k", str(target),
        ])


def ensure_builtin_bgm(outputs: Path) -> list[dict[str, Any]]:
    root = outputs / "audio_scene_assets" / "bgm"
    records: list[dict[str, Any]] = []
    for preset in BGM_PRESETS:
        if not preset.get("generator"):
            records.append({**preset, "url": None, "file": None})
            continue
        target = root / f"{preset['id']}.mp3"
        if not target.exists() or target.stat().st_size < 1000:
            synthesize_original_bgm(target, str(preset["generator"]))
        records.append({
            **preset,
            "file": str(target.relative_to(outputs)),
            "url": "/" + str(target.relative_to(outputs)).replace(" ", "%20"),
            "license": "本專案本機演算法原創，可隨成品使用",
            "audio": audio_probe(target),
        })
    manifest = {"schemaVersion": 1, "generatedAt": utc_now(), "tracks": records}
    atomic_json(root / "manifest.json", manifest)
    return records


def resolve_bgm(outputs: Path, request: dict[str, Any], scene_dir: Path) -> tuple[Path | None, dict[str, Any]]:
    uploaded = str(request.get("uploadedBgmFile", "")).strip()
    if uploaded:
        path = scene_dir / uploaded
        if not path.is_file() or path.parent != scene_dir:
            raise ValueError("找不到上傳的背景音樂")
        info = audio_probe(path)
        return path, {"type": "upload", "name": request.get("uploadedBgmName") or path.name, "file": path.name, "audio": info}
    media_job_id = str(request.get("mediaBgmJobId", "")).strip()
    if media_job_id:
        safe_id = "".join(char for char in media_job_id if char.isalnum() or char in "_-")[:100]
        media_root = outputs / "media_audio_jobs" / safe_id
        manifest_path = media_root / "manifest.json"
        try:
            media_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("找不到已完成的去人聲 BGM 任務") from exc
        bgm_file = (((media_manifest.get("outputs") or {}).get("backgroundMusic") or {}).get("wav") or {}).get("file")
        path = media_root / str(bgm_file or "")
        if not bgm_file or not path.is_file() or path.parent != media_root:
            raise ValueError("媒體任務沒有可用的去人聲 BGM")
        return path, {
            "type": "media-separation",
            "jobId": safe_id,
            "name": f"去人聲｜{media_manifest.get('sourceName', safe_id)}",
            "engine": ((media_manifest.get("outputs") or {}).get("separation") or {}).get("engine"),
            "audio": audio_probe(path),
        }
    preset_id = str(request.get("bgmPresetId", "mountain-qin"))
    preset = get_bgm_preset(preset_id)
    if not preset:
        raise ValueError("找不到指定背景音樂")
    if preset_id == "none":
        return None, {"type": "none", "id": "none", "name": "純人聲"}
    target = outputs / "audio_scene_assets" / "bgm" / f"{preset_id}.mp3"
    if not target.exists():
        ensure_builtin_bgm(outputs)
    return target, {"type": "builtin", "id": preset_id, "name": preset["name"], "license": "本專案本機演算法原創，可隨成品使用", "audio": audio_probe(target)}


def render_audio_scene(
    *, outputs: Path, scene_dir: Path, voice_path: Path, request: dict[str, Any],
    voice_metadata: dict[str, Any], scene_metadata: dict[str, Any],
) -> dict[str, Any]:
    room_id = str(request.get("roomPresetId", "warm-study"))
    if not get_room_preset(room_id):
        raise ValueError("找不到指定空間預設")
    mix_level = str(request.get("musicLevel", "voice-first"))
    if mix_level not in MUSIC_LEVELS:
        raise ValueError("背景音樂音量設定無效")
    intro = max(0.0, min(8.0, float(request.get("introSeconds", 1.4))))
    outro = max(0.5, min(12.0, float(request.get("outroSeconds", 2.6))))
    voice_info = audio_probe(voice_path)
    total = voice_info["durationSeconds"] + intro + outro
    if total > 600:
        raise ValueError("單一聲音場景最長 10 分鐘")
    bgm_path, bgm_metadata = resolve_bgm(outputs, request, scene_dir)
    dry_path = scene_dir / "dry_voice.wav"
    if voice_path.resolve() != dry_path.resolve():
        shutil.copyfile(voice_path, dry_path)
    voice_fx = ROOM_FILTERS[room_id]
    delay_ms = int(round(intro * 1000))
    music_volume = MUSIC_LEVELS[mix_level]
    master_wav = scene_dir / "master.wav"
    master_mp3 = scene_dir / "master.mp3"
    voice_fx_path = scene_dir / "voice_fx.wav"
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(dry_path),
        "-af", f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,highpass=f=65,lowpass=f=15000,acompressor=threshold=0.12:ratio=2.2:attack=15:release=140:makeup=1.25,{voice_fx},alimiter=limit=0.88:level=false",
        "-c:a", "pcm_s24le", str(voice_fx_path),
    ])
    if bgm_path:
        command = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stream_loop", "-1", "-t", f"{total:.3f}", "-i", str(bgm_path), "-i", str(voice_fx_path),
            "-filter_complex",
            (
                f"[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,atrim=0:{total:.3f},"
                f"volume={music_volume:.3f},afade=t=in:st=0:d={min(1.2, max(0.15, intro)):.3f},"
                f"afade=t=out:st={max(0.0, total-outro):.3f}:d={outro:.3f}[music];"
                f"[1:a]adelay={delay_ms}|{delay_ms},apad=pad_dur={outro:.3f},atrim=0:{total:.3f}[voice];"
                "[music][voice]sidechaincompress=threshold=0.025:ratio=8:attack=18:release=420:makeup=1[ducked];"
                "[ducked][voice]amix=inputs=2:duration=longest:normalize=0,"
                "loudnorm=I=-16:TP=-1.5:LRA=9,alimiter=limit=0.84:level=false,asplit=2[wav][mp3]"
            ),
            "-map", "[wav]", "-ar", "48000", "-c:a", "pcm_s24le", str(master_wav),
            "-map", "[mp3]", "-ar", "48000", "-c:a", "libmp3lame", "-b:a", "256k", str(master_mp3),
        ]
    else:
        command = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(voice_fx_path),
            "-filter_complex",
            f"[0:a]adelay={delay_ms}|{delay_ms},apad=pad_dur={outro:.3f},atrim=0:{total:.3f},loudnorm=I=-16:TP=-1.5:LRA=9,alimiter=limit=0.84:level=false,asplit=2[wav][mp3]",
            "-map", "[wav]", "-ar", "48000", "-c:a", "pcm_s24le", str(master_wav),
            "-map", "[mp3]", "-ar", "48000", "-c:a", "libmp3lame", "-b:a", "256k", str(master_mp3),
        ]
    run(command)
    master_info = audio_probe(master_wav)
    qc = loudness_probe(master_wav)
    qc["targetIntegratedLufs"] = -16.0
    qc["targetTruePeakDbfs"] = -1.5
    qc["pass"] = (
        qc.get("integratedLufs") is not None
        and -18.0 <= float(qc["integratedLufs"]) <= -14.0
        and qc.get("truePeakDbfs") is not None
        and float(qc["truePeakDbfs"]) <= -1.0
    )
    manifest = {
        "schemaVersion": 1,
        **scene_metadata,
        "status": "completed",
        "updatedAt": utc_now(),
        "voice": {
            **voice_metadata,
            "dryFile": dry_path.name,
            "fxFile": voice_fx_path.name,
            "dryAudio": audio_probe(dry_path),
            "fxAudio": audio_probe(voice_fx_path),
        },
        "backgroundMusic": bgm_metadata,
        "mix": {
            "musicLevel": mix_level,
            "musicGain": music_volume,
            "ducking": "speech-sidechain-8:1" if bgm_path else "not-applicable",
            "roomPresetId": room_id,
            "introSeconds": intro,
            "outroSeconds": outro,
            "masterTarget": "-16 LUFS / -1.5 dBTP",
        },
        "outputs": {
            "wav": {"file": master_wav.name, **master_info},
            "mp3": {"file": master_mp3.name, **audio_probe(master_mp3)},
        },
        "qualityControl": qc,
    }
    atomic_json(scene_dir / "scene.json", manifest)
    return manifest
