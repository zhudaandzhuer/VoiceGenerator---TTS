#!/usr/bin/env python3
"""Install and download the optional local WeSpeaker embedding runtime."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from paths import resolve_workspace_root


MODEL_REPOSITORY = "Wespeaker/wespeaker-cnceleb-resnet34"
MODEL_REVISION = "c2c6282460dd5958d8eec16785f035d92e4a2d77"
MODEL_FILENAME = "cnceleb_resnet34.onnx"
MODEL_SHA256 = "78817ca21a9707ad886d50745162231027a09c997fbf2ecf741c5d8ff4db1bf8"
MODEL_BYTES = 26_534_127
MODEL_URL = (
    f"https://huggingface.co/{MODEL_REPOSITORY}/resolve/{MODEL_REVISION}/"
    f"{MODEL_FILENAME}?download=true"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare the local WeSpeaker speaker-embedding runtime")
    parser.add_argument("--skip-dependencies", action="store_true", help="Only verify or download the model")
    parser.add_argument("--force", action="store_true", help="Download the pinned model again")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_dependencies() -> None:
    required = {
        "torch": "torch==2.8.0",
        "torchaudio": "torchaudio==2.8.0",
        "onnxruntime": "onnxruntime==1.19.2",
    }
    missing = [package for module, package in required.items() if importlib.util.find_spec(module) is None]
    if not missing:
        print("speaker embedding dependencies: ready")
        return
    print("installing: " + ", ".join(missing))
    subprocess.run([sys.executable, "-m", "pip", "install", "--user", *missing], check=True)


def download_model(target: Path, force: bool = False) -> None:
    if target.exists() and not force and target.stat().st_size == MODEL_BYTES and sha256(target) == MODEL_SHA256:
        print(f"speaker embedding model: ready ({target})")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".download")
    if temporary.exists():
        temporary.unlink()
    print(f"downloading pinned WeSpeaker model ({MODEL_BYTES / 1024 / 1024:.1f} MiB)…")
    request = urllib.request.Request(MODEL_URL, headers={"User-Agent": "VoiceSeedOS/2.0"})
    with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
    actual = sha256(temporary)
    if temporary.stat().st_size != MODEL_BYTES or actual != MODEL_SHA256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("WeSpeaker model checksum mismatch; download was rejected")
    temporary.replace(target)
    metadata = {
        "schemaVersion": 1,
        "provider": "WeSpeaker",
        "repository": MODEL_REPOSITORY,
        "revision": MODEL_REVISION,
        "filename": MODEL_FILENAME,
        "sha256": MODEL_SHA256,
        "bytes": MODEL_BYTES,
        "trainingDataset": "CN-Celeb",
        "input": "16 kHz mono, 80-bin Kaldi fbank with CMN",
        "licenseNote": "WeSpeaker code is Apache-2.0; pretrained weights follow their source dataset license.",
        "source": MODEL_URL,
        "installedAt": datetime.now(timezone.utc).isoformat(),
    }
    metadata_path = target.parent / "model.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"speaker embedding model installed: {target}")


def main() -> int:
    args = parse_args()
    if not args.skip_dependencies:
        install_dependencies()
    root = resolve_workspace_root()
    target = root / "outputs" / "models" / "wespeaker-cnceleb-resnet34" / MODEL_FILENAME
    download_model(target, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
