#!/usr/bin/env python3
"""Build the complete NPC dialogue TTS profile and runtime lookup manifest.

The game never knows about MiMo or API credentials. This development-only
tool scans authored dialogue, assigns stable clip IDs, and emits the two data
files consumed by the synthesis adapter and Godot runtime respectively.
"""

from __future__ import annotations

import json
from pathlib import Path

from paths import resolve_workspace_root

PROJECT_ROOT_DEFAULT = resolve_workspace_root()
DIALOGUE_GLOB = "game/features/*/data/dialogue/*.json"

CHARACTERS = {
    "zhuda": {
        "displayName": "豬大",
        "candidateId": "ZT19",
        "runtimeDialoguePlayback": False,
        "voiceDescription": "二十歲男性，圓亮可愛的玩偶中高音，憨厚柔軟，喜劇節拍清楚，不尖叫、不過度卡通化。",
    },
    "xiaokui": {
        "displayName": "林小葵",
        "candidateId": "XK09",
        "runtimeDialoguePlayback": True,
        "voiceDescription": "二十歲女性，乾淨普通話，音高偏高但圓潤不刺耳，咬字有彈跳感。語速快、情緒明亮，像精力充沛的小太陽，保留成年人自然發音。",
    },
    "xujiao": {
        "displayName": "徐嬌",
        "candidateId": "XJ03",
        "runtimeDialoguePlayback": True,
        "voiceDescription": "二十歲女性，帶自然貴陽年輕口音，聲線清爽結實，音高適中偏亮。咬字俐落，語速正常偏快，冷靜、直接而有生命力。",
    },
    "wanqing": {
        "displayName": "沈晚晴",
        "candidateId": "WQ01",
        "runtimeDialoguePlayback": True,
        "voiceDescription": "二十歲女性，年輕乾淨的普通話，中音偏亮，質地薄而清楚，不用御姐低音或播音腔。反應快，表面冷靜，關心人時語尾自然變柔。",
    },
    "liangqinghan": {
        "displayName": "梁清寒",
        "candidateId": "LQH01",
        "runtimeDialoguePlayback": True,
        "voiceDescription": "二十歲女性，年輕清冷而柔軟的普通話，中高音、氣息輕、咬字乾淨。寡言但不是虛弱或成熟御姐腔，說到流浪動物時明顯變得溫暖。",
    },
}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build production_dialogue profile from dialogue JSON files.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT_DEFAULT,
        help="Workspace root for profile output (default: VOICEGEN_ROOT/VOICEGENERATOR_ROOT/GODOT_MEDIA_PROJECT_ROOT/workspace root)",
    )
    parser.add_argument(
        "--dialogue-glob",
        default=DIALOGUE_GLOB,
        help="Glob pattern to locate dialogue json files. Example: game/features/*/data/dialogue/*.json",
    )
    parser.add_argument(
        "--profile-output",
        type=Path,
        default=None,
        help="Output production dialogue profile path",
    )
    parser.add_argument(
        "--runtime-manifest",
        type=Path,
        default=None,
        help="Runtime dialogue map output path",
    )
    parser.add_argument("--selection-source", default="scripts/profiles/casting_selection.json")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    if args.profile_output is None:
        args.profile_output = project_root / "scripts" / "profiles" / "production_dialogue.json"
    if args.runtime_manifest is None:
        args.runtime_manifest = project_root / "outputs" / "dialogue_voice_manifest.json"

    clips: list[dict[str, object]] = []
    runtime_dialogues: dict[str, dict[str, str]] = {}
    for dialogue_path in sorted(project_root.glob(args.dialogue_glob)):
        payload = json.loads(dialogue_path.read_text(encoding="utf-8"))
        dialogue_id = dialogue_path.stem
        bindings: dict[str, str] = {}
        for node_id, node in payload.get("nodes", {}).items():
            speaker_id = str(node.get("speakerId", ""))
            text = str(node.get("text", "")).strip()
            character = CHARACTERS.get(speaker_id)
            if not character or not character["runtimeDialoguePlayback"] or not text:
                continue
            clip_id = f"{dialogue_id}__{node_id}"
            runtime_path = f"game/characters/{speaker_id}/audio/voice/dialogue/{clip_id}.wav"
            clips.append({
                "id": clip_id,
                "characterId": speaker_id,
                "dialogueId": dialogue_id,
                "nodeId": node_id,
                "text": text,
                "runtimePath": runtime_path,
            })
            bindings[node_id] = f"res://{runtime_path}"
        if bindings:
            runtime_dialogues[dialogue_id] = bindings

    profile = {
        "schemaVersion": 2,
        "provider": "xiaomi_mimo",
        "model": "mimo-v2.5-tts-voicedesign",
        "audioFormat": "wav",
        "selectionSource": args.selection_source,
        "characters": CHARACTERS,
        "clips": clips,
    }
    runtime_manifest = {
        "schemaVersion": 1,
        "generatedBy": "dev/tools/voice/build_dialogue_voice_profile.py",
        "dialogues": runtime_dialogues,
    }
    args.profile_output.parent.mkdir(parents=True, exist_ok=True)
    args.runtime_manifest.parent.mkdir(parents=True, exist_ok=True)
    args.profile_output.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.runtime_manifest.write_text(json.dumps(runtime_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(clips)} voiced NPC lines")
    print(args.profile_output)
    print(args.runtime_manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
