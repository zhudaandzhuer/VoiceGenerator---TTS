#!/usr/bin/env python3
"""Generate the homepage's ancient-drama compound-emotion showcase clips."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path

from generate_tts_catalog import atomic_write, load_local_env
from paths import resolve_workspace_root
from providers.mimo import DEFAULT_BASE_URL, request_audio


ROOT = resolve_workspace_root()
OUTPUT = ROOT / "outputs" / "showcase"
REFERENCE_ROOT = ROOT / "outputs" / "tts_catalog_voice_catalog" / "audio"

SHOWCASE = [
    {
        "id": "ancient_regent",
        "title": "冷面攝政王｜壓抑的愧疚 → 釋然",
        "label": "冷冽權臣的底線",
        "emotions": ["壓抑的憤怒", "愧疚", "苦笑", "釋然"],
        "text": "（壓抑的憤怒，語氣極冷）你以為本王今日來，是要聽你替自己辯解？（停頓，壓低聲音）三年前你跪在雪裡求我救他，我替你擋下那一刀……不是因為你。（苦笑，情緒翻湧）是因為我不願看你，再為任何人低頭。",
        "context": "性別硬性要求：男性。固定成熟男聲，古裝權臣。前段壓抑憤怒，中段帶愧疚與長停頓，最後以苦笑和釋然收束；低沉、克制、字字清楚，不要嘶吼。",
        "referenceVoice": "voice_04",
        "gender": "男性",
    },
    {
        "id": "ancient_general",
        "title": "女將軍｜憤怒 → 委屈 → 動情",
        "label": "戰場歸來的告白",
        "emotions": ["憤怒", "委屈", "動情", "哽咽"],
        "text": "（壓抑的憤怒）你說我不該回來？那一百七十二具棺木，是我親手從北境帶回來的。（哽咽，卻強撐平靜）我沒有哭，不是因為我不痛，是因為全軍都在等我下令。（低聲，動情）可你不一樣……你若叫我留下，我就真的不走了。",
        "context": "性別硬性要求：女性。固定成熟女聲，古裝女將軍。先用壓抑憤怒撐住軍令感，再露出委屈與哽咽，最後轉成克制而真誠的動情告白；保持聲音身份穩定，不得出現男性低沉共鳴。",
        "referenceVoice": "voice_02",
        "gender": "女性",
    },
    {
        "id": "ancient_prince",
        "title": "失勢太子｜無奈 → 忐忑 → 欣慰",
        "label": "雨夜交出玉牌",
        "emotions": ["無奈", "忐忑", "欣慰", "長停頓"],
        "text": "（無奈，輕輕嘆氣）這塊玉牌，你拿著吧。從今以後，宮門內外，再沒有人會替我開路。（忐忑，語速放慢）你不必現在回答我，我只是……想知道，若我不再是太子，你還願不願意陪我走一段？（長停頓，淡淡欣慰）你點頭了。好，那便夠了。",
        "context": "性別硬性要求：男性。固定成熟男聲，古裝失勢太子。語氣從無奈與嘆氣開始，中段忐忑、放慢、欲言又止，最後因得到回答而溫柔欣慰；不哭喊，讓細節靠氣息和停頓表現。",
        "referenceVoice": "voice_04",
        "gender": "男性",
    },
]


def main() -> int:
    load_local_env(ROOT)
    api_key = os.environ.get("MIMO_API_KEY")
    if not api_key:
        raise SystemExit("MIMO_API_KEY is not set")
    base_url = os.environ.get("MIMO_BASE_URL", DEFAULT_BASE_URL)
    overwrite = "--overwrite" in sys.argv
    OUTPUT.mkdir(parents=True, exist_ok=True)
    samples = []
    for item in SHOWCASE:
        reference_path = REFERENCE_ROOT / item["referenceVoice"] / "preset_voice.wav"
        if not reference_path.exists():
            raise SystemExit(f"Missing reference voice: {reference_path}")
        reference = reference_path.read_bytes()
        voice = f"data:audio/wav;base64,{base64.b64encode(reference).decode('ascii')}"
        path = OUTPUT / f"{item['id']}.wav"
        if overwrite or not path.exists():
            print(f"Generating {item['title']}...", flush=True)
            audio = request_audio(
                api_key=api_key,
                base_url=base_url,
                model="mimo-v2.5-tts-voiceclone",
                context=item["context"],
                text=item["text"],
                audio_format="wav",
                timeout=180.0,
                retries=2,
                voice=voice,
            )
            atomic_write(path, audio)
        with wave.open(str(path), "rb") as stream:
            duration_seconds = round(stream.getnframes() / stream.getframerate(), 3) if stream.getframerate() else 0.0
        samples.append({
            "candidateId": item["id"],
            "characterId": item["title"].split("｜", 1)[0],
            "displayName": item["title"].split("｜", 1)[0],
            "label": item["label"],
            "tags": item["emotions"],
            "file": path.name,
            "text": item["text"],
            "voiceDescription": item["context"],
            "seedId": f"{item['referenceVoice']}_preset_reference",
            "voiceDisplay": f"{item['referenceVoice']} · {item['gender']}",
            "gender": item["gender"],
            "model": "mimo-v2.5-tts-voiceclone",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "durationSeconds": duration_seconds,
        })
    manifest = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "provider": "xiaomi_mimo",
        "model": "mimo-v2.5-tts-voiceclone",
        "galleryTitle": "古裝劇複合情緒示範",
        "gallerySubtitle": "用固定聲音參考，演示憤怒、愧疚、委屈、忐忑、動情與釋然的連續轉場。",
        "title": "古裝劇複合情緒示範",
        "subtitle": "固定聲音參考 + 複合情緒 + 句內音頻標籤",
        "candidateCount": len(samples),
        "generatedCount": len(samples),
        "samples": samples,
    }
    atomic_write(OUTPUT / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    cards = []
    for sample in samples:
        tags = " ".join(f"<span>{tag}</span>" for tag in sample["tags"])
        cards.append(f"<article><h2>{sample['label']}</h2><div class='tags'>{tags}</div><audio controls preload='none' src='{sample['file']}'></audio><p>{sample['text']}</p></article>")
    page = """<!doctype html><html lang='zh-Hant'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>古裝劇複合情緒示範</title><style>body{margin:0;background:#201b27;color:#f9f2e8;font-family:-apple-system,BlinkMacSystemFont,'PingFang TC',sans-serif}main{max-width:1100px;margin:auto;padding:36px 20px}article{background:#2c2434;border:1px solid #695263;border-radius:18px;padding:18px;margin:16px 0}h1{font-size:42px}h2{margin-top:0}.tags span{display:inline-block;padding:4px 9px;margin:3px;background:#9e6c58;border-radius:999px;font-size:13px}audio{width:100%;margin:14px 0}p{line-height:1.8;color:#dbcac0;white-space:pre-wrap}</style><main><p><a href='../index.html' style='color:#f0b69b'>← 返回 Voice Seed Studio</a></p><h1>古裝劇複合情緒示範</h1><p>固定參考聲音，以連續情緒和句內標籤完成角色表演。</p>""" + "".join(cards) + "</main></html>"
    atomic_write(OUTPUT / "index.html", page)
    print(f"Showcase ready: {OUTPUT / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
