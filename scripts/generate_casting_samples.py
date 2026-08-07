#!/usr/bin/env python3
"""Generate small, reviewable character casting samples with Xiaomi MiMo TTS.

This development-only adapter deliberately has no dependency on Godot or the
game's dialogue runtime. It reads stable voice-profile JSON and writes WAV plus
a manifest. API credentials are accepted only through MIMO_API_KEY.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from providers.mimo import DEFAULT_BASE_URL, MimoRequestError, request_audio
from paths import resolve_workspace_root, safe_relative

PROJECT_ROOT_DEFAULT = resolve_workspace_root()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate MiMo character casting samples")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT_DEFAULT,
        help="Workspace root for profiles/output (default: VOICEGEN_ROOT/VOICEGENERATOR_ROOT/GODOT_MEDIA_PROJECT_ROOT/workspace root)",
    )
    parser.add_argument("--profiles", type=Path, default=None, help="Path to a casting profile JSON")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory for WAV + manifest")
    parser.add_argument(
        "--character",
        action="append",
        help="Generate only this character ID; repeat to select more than one",
    )
    parser.add_argument("--base-url", default=os.environ.get("MIMO_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()
    args.project_root = args.project_root.resolve()
    if args.profiles is None:
        args.profiles = args.project_root / "scripts" / "profiles" / "casting_round_01.json"
    if args.output_dir is None:
        args.output_dir = args.project_root / "outputs" / "casting_round_01"
    return args


def load_profiles(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    if config.get("schemaVersion") != 1:
        raise ValueError("Unsupported voice-profile schemaVersion")
    if not isinstance(config.get("characters"), dict) or not config["characters"]:
        raise ValueError("Voice-profile file has no characters")
    return config


def inspect_wav(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as stream:
        frames = stream.getnframes()
        sample_rate = stream.getframerate()
        return {
            "channels": stream.getnchannels(),
            "sampleRate": sample_rate,
            "sampleWidthBytes": stream.getsampwidth(),
            "durationSeconds": round(frames / sample_rate, 3) if sample_rate else 0,
        }


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    config = load_profiles(args.profiles.resolve())
    selected = args.character or list(config["characters"].keys())
    unknown = [character_id for character_id in selected if character_id not in config["characters"]]
    if unknown:
        raise ValueError(f"Unknown character IDs: {', '.join(unknown)}")

    output_dir = args.output_dir.resolve()
    if args.dry_run:
        print(json.dumps({"model": config["model"], "characters": selected, "output": str(output_dir)}, ensure_ascii=False, indent=2))
        return 0

    api_key = os.environ.get("MIMO_API_KEY")
    if not api_key:
        print("MIMO_API_KEY is not set", file=sys.stderr)
        return 2

    samples: list[dict[str, Any]] = []
    for character_id in selected:
        profile = config["characters"][character_id]
        output_path = output_dir / f"{character_id}.wav"
        if output_path.exists() and not args.overwrite:
            raise FileExistsError(f"Refusing to overwrite {output_path}; pass --overwrite")
        print(f"Generating {profile['displayName']} ({character_id})...", flush=True)
        audio = request_audio(
            api_key=api_key,
            base_url=args.base_url,
            model=config["model"],
            context=profile["voiceDescription"],
            text=profile["sampleText"],
            audio_format=config.get("audioFormat", "wav"),
            timeout=args.timeout,
            retries=args.retries,
        )
        atomic_write(output_path, audio)
        properties = inspect_wav(output_path)
        samples.append({
            "characterId": character_id,
            "displayName": profile["displayName"],
            "file": output_path.name,
            "text": profile["sampleText"],
            "sha256": hashlib.sha256(audio).hexdigest(),
            **properties,
        })
        print(f"  {output_path.name}: {properties['durationSeconds']}s, {properties['sampleRate']} Hz")

    manifest = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "provider": config["provider"],
        "model": config["model"],
        "profileSource": safe_relative(args.profiles.resolve(), args.project_root),
        "samples": samples,
    }
    manifest_path = output_dir / "manifest.json"
    atomic_write(manifest_path, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, MimoRequestError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
