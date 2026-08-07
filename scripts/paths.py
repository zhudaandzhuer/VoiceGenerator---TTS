"""Path helpers for standalone VoiceGenerator - TTS workspace."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_workspace_root(override: str | Path | None = None) -> Path:
    """Resolve project root for the workspace.

    Priority:
    1. override
    2. environment variables (VOICEGEN_ROOT / VOICEGENERATOR_ROOT / GODOT_MEDIA_PROJECT_ROOT)
    3. directory above this file (scripts/ -> workspace root)
    """
    if override:
        return Path(override).expanduser().resolve()

    for key in ("VOICEGEN_ROOT", "VOICEGENERATOR_ROOT", "GODOT_MEDIA_PROJECT_ROOT"):
        value = os.environ.get(key)
        if value:
            return Path(value).expanduser().resolve()

    return Path(__file__).resolve().parents[1]


def safe_relative(path: Path, base: Path) -> str:
    """Return path relative to base, fallback to absolute string if not possible."""
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)
