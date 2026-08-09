#!/usr/bin/env python3
"""Media-to-audio conversion and model-based vocal separation."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from audio_scene_mixer import audio_probe, loudness_probe, run


SUPPORTED_INPUTS = {
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac",
}


def separator_status() -> dict[str, Any]:
    available = importlib.util.find_spec("demucs") is not None
    return {
        "available": available,
        "engine": "Demucs 4 / htdemucs" if available else None,
        "mode": "model-source-separation" if available else "unavailable",
        "supportsMono": True if available else False,
        "setupCommand": "python3 scripts/setup_audio_tools.py",
    }


def convert_to_mp3(source: Path, target: Path) -> dict[str, Any]:
    if source.suffix.lower() not in SUPPORTED_INPUTS:
        raise ValueError("不支援這個媒體格式")
    target.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source), "-vn",
        "-map", "0:a:0", "-af", "aresample=44100,alimiter=limit=0.95:level=false",
        "-c:a", "libmp3lame", "-b:a", "256k", str(target),
    ], timeout=300.0)
    return {**audio_probe(target), "loudness": loudness_probe(target)}


def separate_vocals(source_mp3: Path, output_dir: Path, *, device: str = "cpu") -> dict[str, Any]:
    status = separator_status()
    if not status["available"]:
        raise RuntimeError("尚未安裝人聲分離模型；請先執行 python3 scripts/setup_audio_tools.py")
    output_dir.mkdir(parents=True, exist_ok=True)
    work = output_dir / "demucs_work"
    command = [
        sys.executable, "-m", "demucs", "--two-stems", "vocals", "-n", "htdemucs",
        "--shifts", "1", "--overlap", "0.25", "--segment", "7", "-j", "1",
        "-d", device, "-o", str(work), str(source_mp3),
    ]
    try:
        subprocess_result = subprocess.run(command, capture_output=True, text=True, timeout=1800, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError("無法啟動 Demucs 人聲分離") from exc
    if subprocess_result.returncode:
        detail = (subprocess_result.stderr or subprocess_result.stdout or "").strip().splitlines()
        raise RuntimeError("人聲分離失敗：" + (detail[-1] if detail else "Demucs error"))
    model_root = work / "htdemucs"
    candidates = list(model_root.glob("*/vocals.wav"))
    if not candidates:
        raise RuntimeError("人聲分離完成但找不到 vocals.wav")
    source_dir = candidates[0].parent
    vocal_source = source_dir / "vocals.wav"
    bgm_source = source_dir / "no_vocals.wav"
    if not bgm_source.exists():
        raise RuntimeError("人聲分離完成但找不到 no_vocals.wav")
    vocals_wav = output_dir / "vocals.wav"
    bgm_wav = output_dir / "bgm_no_vocals.wav"
    shutil.copyfile(vocal_source, vocals_wav)
    shutil.copyfile(bgm_source, bgm_wav)
    vocals_mp3 = output_dir / "vocals.mp3"
    bgm_mp3 = output_dir / "bgm_no_vocals.mp3"
    for source, target in ((vocals_wav, vocals_mp3), (bgm_wav, bgm_mp3)):
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
            "-af", "alimiter=limit=0.95:level=false", "-c:a", "libmp3lame", "-b:a", "256k", str(target),
        ], timeout=300.0)
    shutil.rmtree(work, ignore_errors=True)
    return {
        "engine": status["engine"],
        "model": "htdemucs",
        "vocals": {
            "wav": {"file": vocals_wav.name, **audio_probe(vocals_wav)},
            "mp3": {"file": vocals_mp3.name, **audio_probe(vocals_mp3)},
        },
        "backgroundMusic": {
            "wav": {"file": bgm_wav.name, **audio_probe(bgm_wav)},
            "mp3": {"file": bgm_mp3.name, **audio_probe(bgm_mp3), "loudness": loudness_probe(bgm_mp3)},
        },
    }
