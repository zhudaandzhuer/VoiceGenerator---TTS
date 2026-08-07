#!/usr/bin/env python3
"""Generate a resumable, review-only voice casting gallery."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from providers.mimo import DEFAULT_BASE_URL, MimoRequestError, request_audio
from paths import resolve_workspace_root, safe_relative

PROJECT_ROOT_DEFAULT = resolve_workspace_root()


DEFAULT_PROFILES = PROJECT_ROOT_DEFAULT / "scripts" / "profiles" / "casting_gallery_30.json"
DEFAULT_OUTPUT = PROJECT_ROOT_DEFAULT / "outputs" / "casting_gallery_30"
DEFAULT_SELECTION = PROJECT_ROOT_DEFAULT / "scripts" / "profiles" / "casting_selection.json"
SAFE_ID = re.compile(r"^[A-Z]{2}[0-9]{2}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a MiMo voice casting gallery")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT_DEFAULT,
        help="Workspace root for profile/output (default: VOICEGEN_ROOT/VOICEGENERATOR_ROOT/GODOT_MEDIA_PROJECT_ROOT/workspace root)",
    )
    parser.add_argument("--profiles", type=Path, default=None, help="Path to gallery profile JSON")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory for WAV + manifest HTML")
    parser.add_argument("--selection", type=Path, default=None, help="Path to casting selection JSON")
    parser.add_argument("--candidate", action="append", help="Generate only this candidate ID")
    parser.add_argument("--base-url", default=os.environ.get("MIMO_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()
    args.project_root = args.project_root.resolve()
    if args.profiles is None:
        args.profiles = args.project_root / "scripts" / "profiles" / "casting_gallery_30.json"
    if args.output_dir is None:
        args.output_dir = args.project_root / "outputs" / "casting_gallery_30"
    if args.selection is None:
        args.selection = args.project_root / "scripts" / "profiles" / "casting_selection.json"
    return args


def read_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schemaVersion") != 1:
        raise ValueError("Unsupported gallery schemaVersion")
    characters = config.get("characters")
    candidates = config.get("candidates")
    if not isinstance(characters, dict) or not isinstance(candidates, list):
        raise ValueError("Gallery requires characters and candidates")
    seen: set[str] = set()
    for candidate in candidates:
        candidate_id = candidate.get("id", "")
        if not SAFE_ID.fullmatch(candidate_id) or candidate_id in seen:
            raise ValueError(f"Invalid or duplicate candidate ID: {candidate_id}")
        seen.add(candidate_id)
        if candidate.get("characterId") not in characters:
            raise ValueError(f"Unknown character for {candidate_id}")
        if not candidate.get("voiceDescription") or not candidate.get("label"):
            raise ValueError(f"Incomplete candidate: {candidate_id}")
    return config


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def inspect_wav(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as stream:
        frames = stream.getnframes()
        sample_rate = stream.getframerate()
        if not frames or not sample_rate:
            raise ValueError(f"Empty WAV: {path}")
        return {
            "channels": stream.getnchannels(),
            "sampleRate": sample_rate,
            "sampleWidthBytes": stream.getsampwidth(),
            "durationSeconds": round(frames / sample_rate, 3),
        }


def candidate_hash(config: dict[str, Any], candidate: dict[str, Any]) -> str:
    character = config["characters"][candidate["characterId"]]
    value = json.dumps(
        {
            "model": config["model"],
            "format": config.get("audioFormat", "wav"),
            "description": candidate["voiceDescription"],
            "text": character["sampleText"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def output_path(output_dir: Path, candidate: dict[str, Any]) -> Path:
    return output_dir / candidate["characterId"] / f"{candidate['id'].lower()}.wav"


def read_previous_manifest(output_dir: Path) -> dict[str, Any]:
    path = output_dir / "manifest.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {sample["candidateId"]: sample for sample in data.get("samples", [])}


def collect_samples(
    config: dict[str, Any], output_dir: Path, previous: dict[str, Any], overwrite_ids: set[str]
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for candidate in config["candidates"]:
        path = output_path(output_dir, candidate)
        if not path.exists():
            continue
        profile_hash = candidate_hash(config, candidate)
        old = previous.get(candidate["id"])
        if old and old.get("profileHash") != profile_hash and candidate["id"] not in overwrite_ids:
            raise ValueError(
                f"Profile changed for existing {candidate['id']}; regenerate it with --candidate {candidate['id']} --overwrite"
            )
        audio = path.read_bytes()
        character = config["characters"][candidate["characterId"]]
        samples.append({
            "candidateId": candidate["id"],
            "characterId": candidate["characterId"],
            "displayName": character["displayName"],
            "label": candidate["label"],
            "tags": candidate.get("tags", []),
            "file": str(path.relative_to(output_dir)),
            "text": character["sampleText"],
            "voiceDescription": candidate["voiceDescription"],
            "profileHash": profile_hash,
            "sha256": hashlib.sha256(audio).hexdigest(),
            **inspect_wav(path),
        })
    return samples


def render_readme(config: dict[str, Any], samples: list[dict[str, Any]], selected_ids: set[str]) -> str:
    by_id = {sample["candidateId"]: sample for sample in samples}
    lines = [
        f"# {config.get('galleryTitle', '角色聲線選角廊')}",
        "",
        config.get("gallerySubtitle", "所有候選均使用同角色的相同台詞。請先選音色，不必在這一輪判斷正式演技。"),
        "",
        "建議直接開啟 [網頁播放器](index.html) 連續比較。",
        "",
    ]
    for character_id, character in config["characters"].items():
        lines.extend([f"## {character['displayName']}", ""])
        for candidate in config["candidates"]:
            if candidate["characterId"] != character_id:
                continue
            sample = by_id.get(candidate["id"])
            marker = "✅ " if candidate["id"] in selected_ids else ""
            state = f"[{candidate['id']}｜{candidate['label']}]({sample['file']})" if sample else f"{candidate['id']}｜{candidate['label']}（尚未生成）"
            lines.append(f"- {marker}{state} — {'、'.join(candidate.get('tags', []))}")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_html(config: dict[str, Any], samples: list[dict[str, Any]], selected_ids: set[str]) -> str:
    by_id = {sample["candidateId"]: sample for sample in samples}
    sections: list[str] = []
    for character_id, character in config["characters"].items():
        cards: list[str] = []
        for candidate in config["candidates"]:
            if candidate["characterId"] != character_id:
                continue
            sample = by_id.get(candidate["id"])
            tags = "".join(f"<span>{html.escape(tag)}</span>" for tag in candidate.get("tags", []))
            player = (
                f'<audio controls preload="none" src="{html.escape(sample["file"])}"></audio>'
                if sample else '<p class="pending">尚未生成</p>'
            )
            selected = candidate["id"] in selected_ids
            badge = '<strong class="selected-badge">已入選</strong>' if selected else ""
            card_class = "card selected" if selected else "card"
            cards.append(
                f'<article class="{card_class}">'
                f'<div class="title"><b>{html.escape(candidate["id"])}</b><h3>{html.escape(candidate["label"])}</h3>{badge}</div>'
                f'<div class="tags">{tags}</div>{player}'
                f'<details><summary>聲線設計</summary><p>{html.escape(candidate["voiceDescription"])}</p></details>'
                '</article>'
            )
        sections.append(
            f'<section><h2>{html.escape(character["displayName"])}</h2>'
            f'<p class="script">試音台詞：{html.escape(character["sampleText"])}</p>'
            f'<div class="grid">{"".join(cards)}</div></section>'
        )
    gallery_title = html.escape(config.get("galleryTitle", "角色聲線選角廊"))
    gallery_subtitle = html.escape(config.get("gallerySubtitle", "每位角色使用相同台詞。先挑最像角色的嗓子，正式演技與情緒留到下一輪。"))
    return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>豬大：返金覺醒｜{gallery_title}</title>
<style>
:root{{--ink:#4d2f29;--muted:#81665d;--cream:#fff8ed;--card:#fffdf8;--peach:#f4c6b6;--wood:#986344}}
*{{box-sizing:border-box}} body{{margin:0;background:linear-gradient(145deg,#f8dfcf,#fff8eb 45%,#efd5c8);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"PingFang TC",sans-serif}}
main{{max-width:1180px;margin:auto;padding:36px 20px 70px}} header{{text-align:center;margin-bottom:36px}} h1{{margin:0 0 10px;font-size:clamp(30px,5vw,52px)}} header p,.script{{color:var(--muted)}} section{{margin-top:38px}} h2{{font-size:30px;border-bottom:2px solid var(--peach);padding-bottom:8px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:16px}} .card{{background:rgba(255,253,248,.92);border:1px solid #e7cbbb;border-radius:18px;padding:18px;box-shadow:0 10px 30px rgba(92,52,37,.08)}} .card.selected{{border:3px solid #d78658;background:#fff5df;box-shadow:0 12px 34px rgba(150,85,48,.2)}}
.title{{display:flex;gap:10px;align-items:center}} .title b{{background:var(--wood);color:white;border-radius:9px;padding:5px 8px}} h3{{margin:0;font-size:20px}} .tags{{display:flex;flex-wrap:wrap;gap:6px;margin:13px 0}} .tags span{{font-size:13px;background:#f9e2d6;border-radius:999px;padding:4px 9px}} audio{{width:100%;margin:4px 0 10px}} details{{color:var(--muted);font-size:14px;line-height:1.6}} .pending{{color:#ad8475}}
.selected-badge{{margin-left:auto;background:#d76f43;color:white;border-radius:999px;padding:4px 10px;font-size:13px;white-space:nowrap}}
</style></head><body><main><header><h1>{gallery_title}</h1><p>{gallery_subtitle}</p></header>{''.join(sections)}</main></body></html>"""


def write_gallery(
    config: dict[str, Any],
    output_dir: Path,
    samples: list[dict[str, Any]],
    profile_path: Path,
    selected_ids: set[str],
    project_root: Path,
) -> None:
    manifest = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "provider": config["provider"],
        "model": config["model"],
        "profileSource": safe_relative(profile_path, project_root),
        "candidateCount": len(config["candidates"]),
        "generatedCount": len(samples),
        "samples": samples,
    }
    atomic_write(output_dir / "manifest.json", (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())
    atomic_write(output_dir / "README.md", (render_readme(config, samples, selected_ids) + "\n").encode())
    atomic_write(output_dir / "index.html", render_html(config, samples, selected_ids).encode())


def read_selected_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        item["candidateId"]
        for item in data.get("characters", {}).values()
        if isinstance(item, dict) and item.get("status") == "selected" and item.get("candidateId")
    }


def main() -> int:
    args = parse_args()
    profile_path = args.profiles.resolve()
    output_dir = args.output_dir.resolve()
    config = read_config(profile_path)
    selected_cast_ids = read_selected_ids(args.selection.resolve())
    all_ids = {candidate["id"] for candidate in config["candidates"]}
    selected_ids = set(args.candidate or all_ids)
    unknown = selected_ids - all_ids
    if unknown:
        raise ValueError(f"Unknown candidate IDs: {', '.join(sorted(unknown))}")
    selected = [candidate for candidate in config["candidates"] if candidate["id"] in selected_ids]
    if args.dry_run:
        print(json.dumps({"candidateCount": len(selected), "candidates": [item["id"] for item in selected], "output": str(output_dir)}, ensure_ascii=False, indent=2))
        return 0

    previous = read_previous_manifest(output_dir)
    pending = [candidate for candidate in selected if args.overwrite or not output_path(output_dir, candidate).exists()]
    api_key = os.environ.get("MIMO_API_KEY")
    if pending and not api_key:
        print("MIMO_API_KEY is not set", file=sys.stderr)
        return 2

    overwrite_ids = selected_ids if args.overwrite else set()
    for candidate in pending:
        character = config["characters"][candidate["characterId"]]
        print(f"Generating {candidate['id']} {character['displayName']}｜{candidate['label']}...", flush=True)
        audio = request_audio(
            api_key=api_key,
            base_url=args.base_url,
            model=config["model"],
            context=candidate["voiceDescription"],
            text=character["sampleText"],
            audio_format=config.get("audioFormat", "wav"),
            timeout=args.timeout,
            retries=args.retries,
        )
        path = output_path(output_dir, candidate)
        atomic_write(path, audio)
        properties = inspect_wav(path)
        print(f"  {properties['durationSeconds']}s, {properties['sampleRate']} Hz")
        samples = collect_samples(config, output_dir, previous, overwrite_ids)
        write_gallery(
            config=config,
            output_dir=output_dir,
            samples=samples,
            profile_path=profile_path,
            selected_ids=selected_cast_ids,
            project_root=args.project_root,
        )

    samples = collect_samples(config, output_dir, previous, overwrite_ids)
    write_gallery(
        config=config,
        output_dir=output_dir,
        samples=samples,
        profile_path=profile_path,
        selected_ids=selected_cast_ids,
        project_root=args.project_root,
    )
    print(f"Gallery: {output_dir / 'index.html'} ({len(samples)}/{len(config['candidates'])})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, MimoRequestError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
