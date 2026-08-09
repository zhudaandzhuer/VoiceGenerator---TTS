#!/usr/bin/env python3
"""Transcribe and validate a generated take against its saved dialogue.

This opt-in QA tool uses MiMo-V2.5-ASR.  It never prints the API key and reads
the latest saved generation by default, making it useful for catching spoken
control labels, repeated passages, or a take that drifted away from the script.
"""

from __future__ import annotations

import argparse
import base64
import difflib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from generate_tts_catalog import load_local_env
from paths import resolve_workspace_root


CONTROL_WORDS = {
    "既定情境", "人物關係", "人物目的", "當下目的", "阻力", "潛台詞", "表演節拍",
    "導演補充", "深呼吸", "沉默片刻", "短暫停頓", "急促呼吸", "情緒弧線",
}

# MiMo ASR commonly returns Simplified Chinese even when the source script is
# Traditional Chinese.  Canonicalize the high-frequency variants used by this
# studio before measuring script fidelity; this is deliberately small and
# dependency-free so the one-command project stays portable.
VARIANT_GROUPS = [
    "車车", "來来", "裡裏里", "傘伞", "沒没", "捨舍", "丟丢", "還还", "記记", "讓让",
    "這这", "個个", "為为", "說说", "過过", "點点", "應应", "該该", "會会", "開开",
    "聲声", "對对", "關关", "節节", "體体", "劇剧", "醫医", "師师", "與与", "後后",
    "愛爱", "時時时", "間间", "東东", "書书", "話话", "飲饮", "問问", "錯错", "壓压",
    "將将", "隊队", "橋桥", "樣样", "媽妈", "學学", "寫写", "遠远", "門门", "動动",
    "監监", "視视", "訊讯", "傳传", "號号", "誰谁", "辦办", "處处", "離离", "場场",
    "國国", "藥药", "宮宫", "臺台", "轉转", "錢钱", "繞绕", "帳账", "辭辞", "簽签",
    "證证", "據据", "兒儿", "職职", "業业", "絕绝", "氣气", "實实", "復复", "線线",
    "親亲", "認认", "燈灯", "賣卖", "責责", "調调", "條条", "種种", "層层", "類类",
    "額额", "現现", "潛潜", "詞词", "緒绪", "導导", "員员", "傷伤", "搶抢", "險险",
    "夢梦", "從从", "經经", "終终", "無无", "萬万", "長长", "隨随", "歲岁", "聽听",
]
VARIANT_TRANSLATION = str.maketrans({character: group[-1] for group in VARIANT_GROUPS for character in group})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ASR-check a generated voice take")
    parser.add_argument("--project-root", type=Path, default=resolve_workspace_root())
    parser.add_argument("--audio", type=Path, help="WAV/MP3 path; default is the newest saved take")
    parser.add_argument("--expected", help="Expected dialogue; default is read from the generation manifest")
    parser.add_argument("--min-similarity", type=float, default=0.82)
    return parser.parse_args()


def normalize(text: str) -> str:
    canonical = text.translate(VARIANT_TRANSLATION)
    return "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", canonical)).lower()


def latest_take(root: Path) -> tuple[Path, str, dict[str, Any]]:
    generation_root = root / "outputs" / "voice_generations"
    manifest_path = generation_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    samples = manifest.get("samples", []) if isinstance(manifest, dict) else []
    if not samples:
        raise RuntimeError("沒有可驗收的生成紀錄")
    sample = samples[-1]
    audio_path = generation_root / str(sample.get("file", ""))
    if not audio_path.exists():
        raise RuntimeError(f"找不到生成音檔：{audio_path}")
    return audio_path, str(sample.get("text", "")), sample


def transcribe(root: Path, audio_path: Path) -> str:
    load_local_env(root)
    api_key = os.environ.get("MIMO_API_KEY", "")
    if not api_key:
        raise RuntimeError("MIMO_API_KEY 未設定")
    base_url = os.environ.get("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1").rstrip("/")
    suffix = audio_path.suffix.lower()
    mime = "audio/wav" if suffix == ".wav" else "audio/mpeg" if suffix == ".mp3" else ""
    if not mime:
        raise RuntimeError("ASR 驗收只支援 WAV 或 MP3")
    encoded = base64.b64encode(audio_path.read_bytes()).decode("ascii")
    payload = {
        "model": "mimo-v2.5-asr",
        "messages": [{
            "role": "user",
            "content": [{"type": "input_audio", "input_audio": {"data": f"data:{mime};base64,{encoded}"}}],
        }],
        "asr_options": {"language": "zh"},
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:600]
        raise RuntimeError(f"MiMo ASR HTTP {exc.code}: {detail}") from exc
    try:
        return str(result["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("MiMo ASR 回應缺少轉寫文字") from exc


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    latest_audio, latest_expected, sample = latest_take(root)
    audio_path = args.audio.resolve() if args.audio else latest_audio
    expected = args.expected if args.expected is not None else latest_expected
    transcript = transcribe(root, audio_path)
    expected_norm = normalize(expected)
    transcript_norm = normalize(transcript)
    similarity = difflib.SequenceMatcher(None, expected_norm, transcript_norm).ratio()
    leaked_words = sorted(
        word for word in CONTROL_WORDS
        if normalize(word) in transcript_norm and normalize(word) not in expected_norm
    )
    repeated = bool(expected_norm and len(transcript_norm) > len(expected_norm) * 1.45)
    passed = similarity >= args.min_similarity and not leaked_words and not repeated
    report = {
        "ok": passed,
        "audio": str(audio_path),
        "candidateId": sample.get("candidateId"),
        "expected": expected,
        "transcript": transcript,
        "similarity": round(similarity, 4),
        "controlWordsSpoken": leaked_words,
        "suspectedRepetition": repeated,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
