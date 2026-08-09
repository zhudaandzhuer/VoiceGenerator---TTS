#!/usr/bin/env python3
"""Create fixed voice seeds and one auditable audio take for each hot template.

The local Voice Seed Studio server owns the MiMo credentials and generation
guards. This script only orchestrates its localhost API, then copies each
completed take into ``outputs/hot_templates/`` and writes a small manifest for
the template page.
"""

from __future__ import annotations

import argparse
import json
import shutil
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hot_templates import HOT_TEMPLATES
from paths import resolve_workspace_root
from build_test_dashboard import atomic_write, collect_tests, render_dashboard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate audio for hot voice templates")
    parser.add_argument("--project-root", type=Path, default=resolve_workspace_root())
    parser.add_argument("--base-url", default="http://127.0.0.1:8888")
    parser.add_argument("--force", action="store_true", help="Regenerate existing template audio")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N templates")
    return parser.parse_args()


def request_json(base_url: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base_url.rstrip("/") + path, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{path} 請求失敗：{exc}") from exc
    if not isinstance(body, dict):
        raise RuntimeError(f"{path} 回傳格式錯誤")
    return body


def main() -> int:
    args = parse_args()
    output_root = args.project_root / "outputs"
    template_root = output_root / "hot_templates"
    template_root.mkdir(parents=True, exist_ok=True)
    manifest_path = template_root / "manifest.json"
    manifest = {"schemaVersion": 1, "generatedAt": None, "templates": []}
    if manifest_path.exists():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                manifest.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass
    records = {str(item.get("id")): item for item in manifest.get("templates", []) if isinstance(item, dict)}
    seeds = request_json(args.base_url, "/api/seeds").get("seeds", [])
    seed_by_name = {str(item.get("name")): item for item in seeds if isinstance(item, dict)}
    templates = HOT_TEMPLATES[: args.limit or None]
    for index, template in enumerate(templates, start=1):
        template_id = str(template["id"])
        target_audio = template_root / f"{template_id}.wav"
        existing = records.get(template_id)
        if existing and target_audio.exists() and not args.force:
            print(f"[{index}/{len(templates)}] skip {template_id}（已有音檔）")
            continue
        seed = seed_by_name.get(str(template["seed_name"]))
        if not seed:
            print(f"[{index}/{len(templates)}] 建立聲音種子：{template['seed_name']}")
            seed_response = request_json(args.base_url, "/api/seeds", {
                "kind": "text_design",
                "name": template["seed_name"],
                "gender": template["seed_gender"],
                "description": template["seed_description"],
                "referenceText": template["text"],
            })
            seed = seed_response.get("seed")
            if not isinstance(seed, dict) or not seed.get("id"):
                raise RuntimeError(f"{template_id} 建立種子失敗")
            seed_by_name[str(seed.get("name"))] = seed
        print(f"[{index}/{len(templates)}] 生成音檔：{template['title']}")
        generation = request_json(args.base_url, "/api/generate", {
            "seedId": seed["id"],
            "emotions": template["emotions"],
            "text": template["text"],
            "intensity": template["intensity"],
            "delivery": template["delivery"],
            "pace": template["pace"],
            "pitch": template["pitch"],
            "pause": template["pause"],
            "ending": template["ending"],
            "performanceNote": template["note"],
        }).get("generation")
        if not isinstance(generation, dict) or not generation.get("url"):
            raise RuntimeError(f"{template_id} 生成失敗")
        source_name = Path(urllib.parse.urlparse(str(generation["url"])).path).name
        source_audio = output_root / "voice_generations" / source_name
        if not source_audio.exists():
            raise RuntimeError(f"找不到生成音檔：{source_audio}")
        shutil.copy2(source_audio, target_audio)
        records[template_id] = {
            "id": template_id,
            "audioFile": target_audio.name,
            "candidateId": generation.get("id"),
            "seedId": seed.get("id"),
            "seedName": seed.get("name"),
            "durationSeconds": generation.get("durationSeconds"),
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "status": "ready",
        }
        manifest["templates"] = [records[item["id"]] for item in HOT_TEMPLATES if item["id"] in records]
        manifest["generatedAt"] = datetime.now(timezone.utc).isoformat()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest["templates"] = [records[item["id"]] for item in HOT_TEMPLATES if item["id"] in records]
    manifest["generatedAt"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    atomic_write(output_root / "index.html", render_dashboard(collect_tests(output_root), outputs_root=output_root))
    print(f"完成：{len(manifest['templates'])}/{len(HOT_TEMPLATES)} 個熱門模板音檔")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
