#!/usr/bin/env python3
"""Install the pinned model-based audio-separation dependency."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    print("Installing Demucs 4.0.1 for MP3/video vocal separation…", flush=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--user", "demucs==4.0.1", "soundfile==0.13.1"], check=True)
    print("Ready. The htdemucs model downloads automatically on first separation.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
