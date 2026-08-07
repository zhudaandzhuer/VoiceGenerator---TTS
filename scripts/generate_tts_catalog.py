#!/usr/bin/env python3
"""Generate a resumable MiMo TTS voice/style catalog.

The profile is intentionally data-driven.  Each category is written to its own
outputs/tts_catalog_<category>/ directory so the unified dashboard can keep
adding and switching tests without copying audio or making a second index.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paths import resolve_workspace_root, safe_relative
from providers.mimo import DEFAULT_BASE_URL, MimoRequestError, request_audio


PROJECT_ROOT_DEFAULT = resolve_workspace_root()
DEFAULT_PROFILE = PROJECT_ROOT_DEFAULT / "scripts" / "profiles" / "tts_catalog.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT_DEFAULT / "outputs"
SLUG = re.compile(r"[^a-zA-Z0-9_-]+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the MiMo TTS voice/style catalog")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT_DEFAULT)
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--outputs-root", type=Path, default=None)
    parser.add_argument("--category", action="append", help="Only these category IDs (repeatable)")
    parser.add_argument("--voice", action="append", help="Only these profile voice IDs (repeatable)")
    parser.add_argument("--model", default=None, help="Override profile model")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Generate at most N pending files (0 = unlimited)")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--no-dashboard", action="store_true")
    args = parser.parse_args()
    args.project_root = args.project_root.resolve()
    args.profile = (args.profile or args.project_root / "scripts" / "profiles" / "tts_catalog.json").resolve()
    args.outputs_root = (args.outputs_root or args.project_root / "outputs").resolve()
    return args


def load_local_env(project_root: Path) -> None:
    """Load the private scripts/.env file without requiring python-dotenv."""
    path = project_root / "scripts" / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and value:
            os.environ.setdefault(key, value)


def read_profile(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schemaVersion") != 1:
        raise ValueError("Unsupported tts catalog schemaVersion")
    if not isinstance(data.get("voices"), list) or not data["voices"]:
        raise ValueError("tts catalog requires voices")
    if not isinstance(data.get("categories"), list) or not data["categories"]:
        raise ValueError("tts catalog requires categories")
    voice_ids: set[str] = set()
    for voice in data["voices"]:
        if not voice.get("id") or not voice.get("voice") or voice["id"] in voice_ids:
            raise ValueError(f"Invalid or duplicate voice: {voice}")
        voice_ids.add(voice["id"])
    category_ids: set[str] = set()
    for category in data["categories"]:
        if not category.get("id") or category["id"] in category_ids:
            raise ValueError(f"Invalid or duplicate category: {category}")
        category_ids.add(category["id"])
        if not isinstance(category.get("items"), list) or not category["items"]:
            raise ValueError(f"Category has no items: {category['id']}")
        for item in category["items"]:
            if not item.get("id") or not item.get("label") or not item.get("prompt"):
                raise ValueError(f"Incomplete item in {category['id']}: {item}")
    return data


def slug(value: str) -> str:
    result = SLUG.sub("_", value).strip("_").lower()
    return result or "item"


def atomic_write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data.encode("utf-8") if isinstance(data, str) else data
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
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


def choose_voices(profile: dict[str, Any], category: dict[str, Any], allowed: set[str] | None) -> list[dict[str, Any]]:
    voices = profile["voices"]
    if allowed:
        voices = [voice for voice in voices if voice["id"] in allowed]
    mode = category.get("voiceMode", "reference")
    if mode == "all":
        return voices
    if mode == "reference":
        preferred = ["voice_01", "voice_03"]
        selected = [voice for voice in voices if voice["id"] in preferred]
        return selected or voices[:2]
    raise ValueError(f"Unsupported voiceMode {mode} in {category['id']}")


def build_plan(profile: dict[str, Any], category: dict[str, Any], allowed_voices: set[str] | None) -> list[dict[str, Any]]:
    text_map = profile.get("texts", {})
    plan: list[dict[str, Any]] = []
    for voice in choose_voices(profile, category, allowed_voices):
        for item in category["items"]:
            text_key = item.get("textKey", category.get("textKey", "neutral"))
            text = item.get("inline") or text_map.get(text_key, text_map.get("neutral", "你好。"))
            candidate_id = f"{voice['id']}__{item['id']}"
            voice_display = voice.get("displayVoice", voice["voice"])
            plan.append({
                "candidateId": candidate_id,
                "voiceId": voice["id"],
                "voice": voice["voice"],
                "voiceDisplay": voice_display,
                "voiceName": f"{voice_display}｜{voice['gender']}｜{voice['language']}",
                "voiceProfile": voice.get("profile", ""),
                "itemId": item["id"],
                "label": item["label"],
                "prompt": item["prompt"],
                "text": text,
                "styleTag": item.get("tag", ""),
                "tags": list(dict.fromkeys(list(voice.get("tags", [])) + list(item.get("tags", [])))),
            })
    return plan


def profile_hash(profile: dict[str, Any], category: dict[str, Any], candidate: dict[str, Any]) -> str:
    value = json.dumps({
        "model": profile["model"],
        "category": category["id"],
        "voice": candidate["voice"],
        "prompt": candidate["prompt"],
        "text": candidate["text"],
        "styleTag": candidate["styleTag"],
    }, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def output_path(output_dir: Path, candidate: dict[str, Any]) -> Path:
    return output_dir / "audio" / slug(candidate["voiceId"]) / f"{slug(candidate['itemId'])}.wav"


def read_previous(output_dir: Path) -> dict[str, Any]:
    path = output_dir / "manifest.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(item.get("candidateId")): item for item in data.get("samples", []) if item.get("candidateId")}


def collect_samples(profile: dict[str, Any], category: dict[str, Any], output_dir: Path, plan: list[dict[str, Any]], previous: dict[str, Any]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for candidate in plan:
        path = output_path(output_dir, candidate)
        if not path.exists():
            continue
        expected_hash = profile_hash(profile, category, candidate)
        old = previous.get(candidate["candidateId"])
        if old and old.get("profileHash") != expected_hash:
            raise ValueError(f"Profile changed for {candidate['candidateId']}; rerun with --overwrite")
        details = inspect_wav(path)
        samples.append({
            "candidateId": candidate["candidateId"],
            "characterId": candidate.get("voiceDisplay", candidate["voiceId"]),
            "displayName": candidate["voiceName"],
            "label": candidate["label"],
            "tags": candidate["tags"],
            "file": str(path.relative_to(output_dir)),
            "text": candidate["text"],
            "voiceDescription": candidate["prompt"],
            "voice": candidate["voice"],
            "voiceDisplay": candidate.get("voiceDisplay", candidate["voice"]),
            "voiceProfile": candidate["voiceProfile"],
            "styleTag": candidate["styleTag"],
            "profileHash": expected_hash,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            **details,
        })
    return samples


def render_category_html(profile: dict[str, Any], category: dict[str, Any], samples: list[dict[str, Any]]) -> str:
    cards: list[str] = []
    for sample in samples:
        tags = "".join(f'<span>{html.escape(str(tag))}</span>' for tag in sample.get("tags", []))
        cards.append(
            '<article class="card">'
            f'<div class="title"><b>{html.escape(sample.get("voiceDisplay", sample["voice"]))}</b><h3>{html.escape(sample["label"])}</h3></div>'
            f'<p class="meta">{html.escape(sample["displayName"])}｜{sample["durationSeconds"]:.2f}s</p>'
            f'<div class="tags">{tags}</div>'
            f'<audio controls preload="none" src="{html.escape(sample["file"])}"></audio>'
            f'<p class="text">台詞：{html.escape(sample["text"])}</p>'
            f'<details><summary>生成指令</summary><p>{html.escape(sample["voiceDescription"])}</p></details>'
            '</article>'
        )
    title = html.escape(category["title"])
    subtitle = html.escape(category.get("subtitle", ""))
    cards_html = "".join(cards)
    return f"""<!doctype html><html lang=\"zh-Hant\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{title}</title><style>
:root{{--ink:#402a25;--muted:#7e6258;--bg:#f7e3d6;--paper:#fffdf8;--line:#e5cabc;--accent:#b76642}}*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(135deg,#f8dfcf,#fff8eb 48%,#efd5c8);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,\"PingFang TC\",sans-serif}}main{{max-width:1240px;margin:auto;padding:32px 20px 70px}}header{{margin-bottom:28px}}h1{{margin:0 0 8px;font-size:clamp(28px,4vw,46px)}}header p{{color:var(--muted);line-height:1.7}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}}.card{{background:rgba(255,253,248,.94);border:1px solid var(--line);border-radius:18px;padding:16px;box-shadow:0 10px 28px #6a403018}}.title{{display:flex;align-items:center;gap:10px}}.title b{{background:var(--accent);color:white;border-radius:999px;padding:5px 9px;font-size:13px}}h3{{margin:0;font-size:19px}}.meta,.text,details{{font-size:14px;line-height:1.6;color:var(--muted)}}.tags{{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}}.tags span{{background:#f7dfd2;border-radius:999px;padding:4px 8px;font-size:12px}}audio{{width:100%;margin:5px 0 8px}}details p{{margin-bottom:0}}</style></head><body><main><header><h1>{title}</h1><p>{subtitle}</p><p>已生成 {len(samples)} 個樣本。可以回到 <a href=\"../index.html\">總覽</a> 切換其他測試。</p></header><div class=\"grid\">{cards_html}</div></main></body></html>"""


def write_outputs(profile: dict[str, Any], category: dict[str, Any], output_dir: Path, samples: list[dict[str, Any]], plan: list[dict[str, Any]], profile_path: Path, project_root: Path, errors: list[dict[str, str]]) -> None:
    manifest = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "provider": profile["provider"],
        "model": profile["model"],
        "galleryTitle": category["title"],
        "gallerySubtitle": category.get("subtitle", ""),
        "title": category["title"],
        "subtitle": category.get("subtitle", ""),
        "categoryId": category["id"],
        "profileSource": safe_relative(profile_path, project_root),
        "source": profile.get("source", {}),
        "candidateCount": len(plan),
        "generatedCount": len(samples),
        "errors": errors,
        "samples": samples,
    }
    atomic_write(output_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    atomic_write(output_dir / "index.html", render_category_html(profile, category, samples))
    readme = [f"# {category['title']}", "", category.get("subtitle", ""), "", f"已生成 {len(samples)}/{len(plan)} 個樣本。", "", "音檔與 manifest 由 `generate_tts_catalog.py` 可續跑生成。", ""]
    atomic_write(output_dir / "README.md", "\n".join(readme))


def rebuild_dashboard(project_root: Path) -> None:
    script = project_root / "scripts" / "build_test_dashboard.py"
    subprocess.run([sys.executable, str(script), "--project-root", str(project_root)], check=True)


def main() -> int:
    args = parse_args()
    load_local_env(args.project_root)
    profile = read_profile(args.profile)
    if args.model:
        profile["model"] = args.model
    requested_categories = set(args.category or [])
    categories = [category for category in profile["categories"] if not requested_categories or category["id"] in requested_categories]
    unknown_categories = requested_categories - {category["id"] for category in profile["categories"]}
    if unknown_categories:
        raise ValueError(f"Unknown categories: {', '.join(sorted(unknown_categories))}")
    allowed_voices = set(args.voice or []) or None
    all_voice_ids = {voice["id"] for voice in profile["voices"]}
    if allowed_voices and not allowed_voices <= all_voice_ids:
        raise ValueError(f"Unknown voice IDs: {', '.join(sorted(allowed_voices - all_voice_ids))}")

    plans = {category["id"]: build_plan(profile, category, allowed_voices) for category in categories}
    total = sum(len(plan) for plan in plans.values())
    if args.dry_run:
        print(json.dumps({"model": profile["model"], "categories": {category["id"]: len(plans[category["id"]]) for category in categories}, "total": total, "outputsRoot": str(args.outputs_root)}, ensure_ascii=False, indent=2))
        return 0

    api_key = os.environ.get("MIMO_API_KEY")
    if not api_key:
        print("MIMO_API_KEY is not set (also checked scripts/.env)", file=sys.stderr)
        return 2
    base_url = args.base_url or os.environ.get("MIMO_BASE_URL", DEFAULT_BASE_URL)
    generated_now = 0
    failures = 0
    remaining_limit = args.limit if args.limit > 0 else None

    for category in categories:
        output_dir = args.outputs_root / f"tts_catalog_{slug(category['id'])}"
        plan = plans[category["id"]]
        # In overwrite mode the new profile is authoritative; do not reject
        # old hashes while rebuilding the category manifest.
        previous = {} if args.overwrite else read_previous(output_dir)
        errors: list[dict[str, str]] = []
        pending: list[dict[str, Any]] = []
        for candidate in plan:
            path = output_path(output_dir, candidate)
            if path.exists() and not args.overwrite:
                continue
            if remaining_limit is not None and remaining_limit <= 0:
                break
            pending.append(candidate)
            if remaining_limit is not None:
                remaining_limit -= 1
        print(f"[{category['id']}] {len(pending)} pending / {len(plan)} total", flush=True)

        for candidate in pending:
            path = output_path(output_dir, candidate)
            try:
                print(f"  生成 {candidate['candidateId']}｜{candidate['voice']}｜{candidate['label']}...", flush=True)
                audio = request_audio(
                    api_key=api_key,
                    base_url=base_url,
                    model=profile["model"],
                    context=candidate["prompt"],
                    text=candidate["text"],
                    audio_format=profile.get("audioFormat", "wav"),
                    timeout=args.timeout,
                    retries=args.retries,
                    voice=candidate["voice"],
                )
                atomic_write(path, audio)
                details = inspect_wav(path)
                generated_now += 1
                print(f"    {details['durationSeconds']}s, {details['sampleRate']} Hz", flush=True)
            except (OSError, MimoRequestError, RuntimeError, ValueError) as exc:
                failures += 1
                errors.append({"candidateId": candidate["candidateId"], "error": str(exc)})
                print(f"    失敗：{exc}", file=sys.stderr, flush=True)
            samples = collect_samples(profile, category, output_dir, plan, previous)
            write_outputs(profile, category, output_dir, samples, plan, args.profile, args.project_root, errors)

        samples = collect_samples(profile, category, output_dir, plan, previous)
        write_outputs(profile, category, output_dir, samples, plan, args.profile, args.project_root, errors)
        print(f"  完成 {len(samples)}/{len(plan)} → {output_dir}", flush=True)

    if not args.no_dashboard:
        rebuild_dashboard(args.project_root)
    print(f"Catalog complete: generated_now={generated_now}, failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
