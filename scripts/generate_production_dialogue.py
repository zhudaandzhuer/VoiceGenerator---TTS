#!/usr/bin/env python3
"""Generate selected production dialogue clips through the MiMo adapter."""

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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT_DEFAULT,
        help="Workspace root for profile/output (default: VOICEGEN_ROOT/VOICEGENERATOR_ROOT/GODOT_MEDIA_PROJECT_ROOT/workspace root)",
    )
    parser.add_argument("--profiles", type=Path, default=None, help="Path to production dialogue profile JSON")
    parser.add_argument("--clip", action="append")
    parser.add_argument("--base-url", default=os.environ.get("MIMO_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--manifest-output", type=Path, default=None, help="Manifest output path")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()
    args.project_root = args.project_root.resolve()
    if args.profiles is None:
        args.profiles = args.project_root / "scripts" / "profiles" / "production_dialogue.json"
    if args.manifest_output is None:
        args.manifest_output = args.project_root / "outputs" / "production_manifest.json"
    return args


def resolve_runtime_path(project_root: Path, runtime_path: str) -> Path:
    path = Path(runtime_path)
    if path.is_absolute():
        return path
    return project_root / path


def inspect_wav(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as stream:
        frames = stream.getnframes()
        rate = stream.getframerate()
        return {"durationSeconds": round(frames / rate, 3), "sampleRate": rate, "channels": stream.getnchannels()}


def main() -> int:
    args = parse_args()
    config = json.loads(args.profiles.read_text(encoding="utf-8"))
    clips = config.get("clips", [])
    if args.clip:
        requested = set(args.clip)
        clips = [clip for clip in clips if clip.get("id") in requested]
        missing = requested - {clip.get("id") for clip in clips}
        if missing:
            raise ValueError(f"Unknown clip IDs: {', '.join(sorted(missing))}")
    if args.dry_run:
        print(json.dumps({"model": config["model"], "clips": [clip["id"] for clip in clips]}, ensure_ascii=False, indent=2))
        return 0
    api_key = os.environ.get("MIMO_API_KEY")
    if not api_key:
        print("MIMO_API_KEY is not set", file=sys.stderr)
        return 2
    records: list[dict[str, Any]] = []
    for clip in clips:
        character = config["characters"][clip["characterId"]]
        target = resolve_runtime_path(args.project_root, clip["runtimePath"])
        if target.exists() and not args.overwrite:
            audio = target.read_bytes()
        else:
            print(f"Generating {clip['id']} ({character['candidateId']})...", flush=True)
            audio = request_audio(
                api_key=api_key,
                base_url=args.base_url,
                model=config["model"],
                context=character["voiceDescription"],
                text=clip["text"],
                audio_format=config.get("audioFormat", "wav"),
                timeout=args.timeout,
                retries=args.retries,
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(".wav.tmp")
            temporary.write_bytes(audio)
            temporary.replace(target)
        records.append({
            "clipId": clip["id"],
            "characterId": clip["characterId"],
            "candidateId": character["candidateId"],
            "runtimePath": clip["runtimePath"],
            "text": clip["text"],
            "sha256": hashlib.sha256(audio).hexdigest(),
            **inspect_wav(target),
        })
    manifest = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "provider": config["provider"],
        "model": config["model"],
        "profileSource": safe_relative(args.profiles.resolve(), args.project_root),
        "clips": records,
    }
    output = args.manifest_output
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, MimoRequestError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
