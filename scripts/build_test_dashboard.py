#!/usr/bin/env python3
"""Build a unified dashboard for all generated voice-test manifests.

This script scans outputs/*/manifest.json and generates one production page:
`outputs/index.html`.  The left rail is reserved for generated-take history;
raw test manifests stay on disk but do not compete with the voice workbench.
"""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from paths import resolve_workspace_root


PROJECT_ROOT_DEFAULT = resolve_workspace_root()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build unified voice dashboard")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT_DEFAULT,
        help="Workspace root for outputs/ and scripts/",
    )
    parser.add_argument(
        "--outputs-root",
        type=Path,
        default=None,
        help="Outputs root directory (default: <project-root>/outputs)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output index file (default: <outputs-root>/index.html)",
    )
    return parser.parse_args()


def safe_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    if not isinstance(value, str):
        return fallback if value is None else str(value)
    return value


def safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.fromtimestamp(0)
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.fromtimestamp(0)


def atomic_write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data.encode("utf-8") if isinstance(data, str) else data
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)


def safe_group(samples: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for sample in samples:
        char_id = str(sample.get("characterId", "unknown")).strip() or "unknown"
        grouped.setdefault(char_id, []).append(sample)
    for items in grouped.values():
        items.sort(key=lambda item: str(item.get("label", "")))
    return grouped


# Keep the navigation focused on production-useful views.  The raw catalog
# manifests remain on disk and can still be opened directly when needed.
VISIBLE_TESTS = {
    "voice_generations",
    "tts_catalog_voice_catalog",
}


def render_dashboard(test_data: list[dict[str, Any]], outputs_root: Path | None = None) -> str:
    total_samples = sum(test["generatedCount"] for test in test_data)
    compound_emotions = [
        "平靜", "喜悅", "得意", "悲傷", "憤怒", "恐懼", "驚訝", "厭惡",
        "怅然", "欣慰", "無奈", "愧疚", "釋然", "嫉妒", "厭倦",
        "忐忑", "動情", "委屈", "壓抑的憤怒", "冷笑", "決絕",
        "溫柔", "欲言又止", "如釋重負", "哽咽",
    ]
    emotion_chips = "".join(
        f'<button type="button" class="emotion-chip" data-emotion="{html.escape(emotion)}">{html.escape(emotion)}</button>'
        for emotion in compound_emotions
    )
    theme_templates = [
        {
            "id": "ancient",
            "name": "古裝月影",
            "swatches": ["#2b2135", "#c86f61", "#f1b89f"],
        },
        {
            "id": "cinema",
            "name": "電影暗幕",
            "swatches": ["#171923", "#d66b52", "#f2c078"],
        },
        {
            "id": "daylight",
            "name": "清透日光",
            "swatches": ["#f6f1e8", "#4b9b91", "#e4a15d"],
        },
        {
            "id": "neon",
            "name": "霓虹聲場",
            "swatches": ["#11152d", "#e85aa5", "#52d5cf"],
        },
    ]
    theme_options = []
    for template in theme_templates:
        swatches = "".join(
            f'<span class="template-swatch" style="--swatch:{html.escape(color)}"></span>'
            for color in template["swatches"]
        )
        theme_options.append(
            f'<button type="button" class="theme-option" data-template="{html.escape(template["id"])}" '
            f'aria-pressed="false"><span class="template-swatches">{swatches}</span><span>'
            f'<strong>{html.escape(template["name"])}'
            f'</strong><small>切換工作站配色</small></span><span class="theme-option-check">✓</span></button>'
        )
    theme_options_html = "".join(theme_options)
    hot_templates = [
        {
            "id": "regent-confession",
            "title": "冷面攝政王｜壓抑的愧疚 → 釋然",
            "label": "古裝權謀 · 一句就能上戲",
            "text": "你以為本王今日來，是要聽你替自己辯解？三年前你跪在雪裡求我救他，我替你擋下那一刀……不是因為你。是因為我不願看你，再為任何人低頭。",
            "emotions": ["壓抑的憤怒", "愧疚", "釋然"],
            "intensity": "明顯", "delivery": "古裝台詞", "pace": "忽快忽慢", "pitch": "先低後高", "pause": "句尾留白", "ending": "情緒停住但不截斷",
            "note": "前半壓住怒火，第二句帶一點哽咽，最後一句放柔。",
            "tags": ["熱門", "權謀", "情緒轉場"],
        },
        {
            "id": "general-return",
            "title": "女將軍｜憤怒 → 委屈 → 動情",
            "label": "戰場歸來的告白",
            "text": "你說我不該回來？那一百七十二具棺木，是我親手從北境帶回來的。我沒有哭，不是因為我不痛，是因為全軍都在等我下令。可你不一樣……你若叫我留下，我就真的不走了。",
            "emotions": ["憤怒", "委屈", "動情"],
            "intensity": "明顯", "delivery": "古裝台詞", "pace": "忽快忽慢", "pitch": "先低後高", "pause": "長停頓", "ending": "尾音放輕",
            "note": "第一句帶戰場餘怒，中段壓住哭腔，最後一句只留一口氣。",
            "tags": ["女聲", "告白", "哽咽"],
        },
        {
            "id": "midnight-message",
            "title": "凌晨訊息｜冷靜 → 崩潰 → 挽留",
            "label": "現代情感 · 內心獨白",
            "text": "我只是想問你，到家了嗎？……算了，你不用回。我已經把你的東西都收好了，可那盞燈我還是不敢關。你今晚若還願意回來，我就當作什麼都沒有發生。",
            "emotions": ["無奈", "悲傷", "動情"],
            "intensity": "克制", "delivery": "內心獨白", "pace": "慢速", "pitch": "先高後低", "pause": "長停頓", "ending": "欲言又止",
            "note": "像對著未讀訊息說話，前半故作平靜，最後一句不要哭喊。",
            "tags": ["現代", "夜戲", "挽留"],
        },
        {
            "id": "mystery-vow",
            "title": "懸疑誓言｜恐懼 → 決絕",
            "label": "低語耳語 · 最後一字要落地",
            "text": "門外那個人，不是我哥。你現在離開還來得及，別回頭，也別問我為什麼知道。若天亮以前我沒有出去，就把這段錄音交給警察。",
            "emotions": ["恐懼", "忐忑", "決絕"],
            "intensity": "強烈但不破音", "delivery": "低語耳語", "pace": "標準", "pitch": "偏低沉", "pause": "斷續哽咽", "ending": "完整收句",
            "note": "貼近麥克風的壓低聲線，恐懼藏在呼吸裡，最後一句清楚收住。",
            "tags": ["懸疑", "低語", "反轉"],
        },
    ]
    # Keep the catalogue in one source of truth. The local definitions above
    # remain a safe fallback for direct imports, while generated audio metadata
    # is merged from outputs/hot_templates/manifest.json when available.
    try:
        from hot_templates import THEME_TEMPLATES, load_hot_templates
        theme_templates = THEME_TEMPLATES
        hot_templates = load_hot_templates(outputs_root)
    except ImportError:
        pass
    hot_template_cards = []
    for item in hot_templates:
        emotion_tags = "".join(f'<span class="tag warm">{html.escape(tag)}</span>' for tag in item["emotions"])
        extra_tags = "".join(f'<span class="hot-template-tag">{html.escape(tag)}</span>' for tag in item["tags"])
        audio_file = str(item.get("audioFile", "")).strip()
        audio_html = f'<audio controls preload="none" src="hot_templates/{html.escape(audio_file)}"></audio>' if audio_file else '<div class="hot-template-audio-missing">音檔尚未生成</div>'
        data_attrs = (
            f'data-hot-template="{html.escape(item["id"])}" '
            f'data-text="{html.escape(item["text"], quote=True)}" '
            f'data-emotions="{html.escape("|".join(item["emotions"]), quote=True)}" '
            f'data-intensity="{html.escape(item["intensity"])}" data-delivery="{html.escape(item["delivery"])}" '
            f'data-pace="{html.escape(item["pace"])}" data-pitch="{html.escape(item["pitch"])}" '
            f'data-pause="{html.escape(item["pause"])}" data-ending="{html.escape(item["ending"])}" '
            f'data-note="{html.escape(item["note"], quote=True)}"'
        )
        hot_template_cards.append(
            f'<article class="hot-template-card"><div class="hot-template-top"><span class="hot-template-kicker">熱門台詞模板</span>'
            f'<span class="hot-template-tags">{extra_tags}</span></div><h3>{html.escape(item["title"])}</h3>'
            f'<p class="hot-template-label">{html.escape(item["label"])}</p><div class="tags">{emotion_tags}</div>{audio_html}'
            f'<p class="hot-template-text">{html.escape(item["text"])}</p>'
            f'<small class="hot-template-config">{html.escape(item["delivery"])} · {html.escape(item["pace"])} · {html.escape(item["intensity"])}</small>'
            f'<button type="button" class="primary-btn hot-template-use" {data_attrs}>套用並生成</button></article>'
        )
    hot_templates_html = "".join(hot_template_cards)
    featured = [
        {
            "title": "冷面攝政王｜壓抑的愧疚 → 釋然",
            "label": "冷冽權臣的底線",
            "audio": "showcase/ancient_regent.wav",
            "tags": ["壓抑的憤怒", "愧疚", "苦笑", "釋然"],
            "text": "你以為本王今日來，是要聽你替自己辯解？\n三年前你跪在雪裡求我救他，我替你擋下那一刀……不是因為你。\n是因為我不願看你，再為任何人低頭。",
        },
        {
            "title": "女將軍｜憤怒 → 委屈 → 動情",
            "label": "戰場歸來的告白",
            "audio": "showcase/ancient_general.wav",
            "tags": ["憤怒", "委屈", "動情", "哽咽"],
            "text": "你說我不該回來？那一百七十二具棺木，是我親手從北境帶回來的。\n我沒有哭，不是因為我不痛，是因為全軍都在等我下令。\n可你不一樣……你若叫我留下，我就真的不走了。",
        },
        {
            "title": "失勢太子｜無奈 → 忐忑 → 欣慰",
            "label": "雨夜交出玉牌",
            "audio": "showcase/ancient_prince.wav",
            "tags": ["無奈", "忐忑", "欣慰", "長停頓"],
            "text": "這塊玉牌，你拿著吧。從今以後，宮門內外，再沒有人會替我開路。\n你不必現在回答我，我只是……想知道，若我不再是太子，你還願不願意陪我走一段？\n你點頭了。好，那便夠了。",
        },
    ]
    showcase_cards = []
    for item in featured:
        tags = "".join(f'<span class="tag warm">{html.escape(tag)}</span>' for tag in item["tags"])
        showcase_cards.append(
            '<article class="showcase-card">'
            f'<div class="showcase-kicker">古裝劇複合情緒示範</div><h3>{html.escape(item["title"])}</h3>'
            f'<p class="showcase-label">{html.escape(item["label"])}</p><div class="tags">{tags}</div>'
            f'<audio controls preload="none" src="{html.escape(item["audio"])}"></audio>'
            f'<p class="showcase-text">{html.escape(item["text"])}</p>'
            f'<button type="button" class="ghost-btn showcase-load" data-text="{html.escape(item["text"], quote=True)}">載入這段台詞</button>'
            '</article>'
        )

    history_samples: list[dict[str, Any]] = []
    for test in test_data:
        if test.get("id") != "voice_generations":
            continue
        for items in test.get("groups", {}).values():
            history_samples.extend(items)
    history_samples.sort(key=lambda item: parse_time(safe_text(item.get("createdAt"))), reverse=True)
    history_cards: list[str] = []
    for sample in history_samples[:30]:
        sample_id = safe_text(sample.get("candidateId"), "語音生成")
        seed_name = safe_text(sample.get("voiceDisplay") or sample.get("seedName") or sample.get("displayName"), "聲音種子")
        gender = safe_text(sample.get("gender"), "不指定")
        label = safe_text(sample.get("label"), "平靜")
        text = safe_text(sample.get("text"), "")
        duration = safe_float(sample.get("durationSeconds"))
        created = parse_time(safe_text(sample.get("createdAt"))).strftime("%m/%d %H:%M")
        file_rel = safe_text(sample.get("file"), "")
        src = f"voice_generations/{file_rel}" if file_rel else ""
        tags = "".join(f'<span class="tag tiny">{html.escape(str(tag))}</span>' for tag in sample.get("tags", [])[:4])
        audio = f'<audio controls preload="none" src="{html.escape(src)}"></audio>' if src else ""
        history_cards.append(
            '<article class="history-card" data-history-id="' + html.escape(sample_id) + '">'
            f'<div class="history-top"><span class="history-state done">已完成</span><time>{html.escape(created)}</time></div>'
            f'<strong>{html.escape(seed_name)}</strong>'
            f'<small>{html.escape(gender)} · {html.escape(label)} · {duration:.2f}s</small>'
            f'<div class="tags">{tags}</div>{audio}'
            f'<p>{html.escape(text)}</p>'
            f'<button type="button" class="history-load" data-history-text="{html.escape(text, quote=True)}">帶入台詞</button>'
            '</article>'
        )
    history_html = "".join(history_cards) or '<div class="history-empty" id="history-empty">尚未生成。每次完成的語音都會固定出現在這裡。</div>'

    style_html = """
  :root {
    --ink:#3f2b31;--muted:#7c6567;--bg:#f7e2d4;--paper:#fffdf8;--card:#fffdf9;
    --card-bd:#e7cbc0;--peach:#f1b89f;--wood:#986344;--plum:#2b2135;--plum-2:#4b354d;
    --rose:#c86f61;--gold:#d6a35e;--mint:#8bb6a7;
  }
  *{box-sizing:border-box}
  body{margin:0;background:linear-gradient(135deg,#f7dfcf,#fff8eb 46%,#eed3cb);color:var(--ink);font-family:-apple-system,"PingFang TC",Arial,sans-serif;transition:background .35s ease,color .25s ease}
  body[data-template="cinema"]{--ink:#33282e;--muted:#82676a;--card:#fffaf5;--card-bd:#dfb9ad;--plum:#171923;--plum-2:#362934;--rose:#c75f4c;--wood:#8b4d3f;--peach:#f0b780;background:linear-gradient(135deg,#e8d7d2,#fbf2e8 48%,#d8c1c4)}
  body[data-template="cinema"] .hero{background:radial-gradient(circle at 84% 10%,#d66b5255,transparent 32%),linear-gradient(135deg,#171923,#362934 58%,#70434b)}
  body[data-template="cinema"] .showcase-card{background:linear-gradient(145deg,#171923,#362934);border-color:#8c5a5d}
  body[data-template="daylight"]{--ink:#254247;--muted:#587276;--card:#fffefa;--card-bd:#c7ddd6;--plum:#214e52;--plum-2:#367b78;--rose:#4b9b91;--wood:#a36f3c;--peach:#e4a15d;background:linear-gradient(135deg,#e9f1ec,#fffdf5 48%,#dcebe5)}
  body[data-template="daylight"] .hero{background:radial-gradient(circle at 84% 10%,#e4a15d66,transparent 34%),linear-gradient(135deg,#214e52,#367b78 58%,#6fa69a)}
  body[data-template="daylight"] .showcase-card{background:linear-gradient(145deg,#214e52,#367b78);border-color:#83b9ab}
  body[data-template="neon"]{--ink:#e7e9f2;--muted:#aeb7ce;--card:#1b203b;--card-bd:#414b78;--plum:#11152d;--plum-2:#242b58;--rose:#e85aa5;--wood:#52d5cf;--peach:#f2a7d0;background:radial-gradient(circle at 80% 5%,#e85aa522,transparent 28%),linear-gradient(135deg,#0c1022,#11152d 48%,#1d1640)}
  body[data-template="neon"] .sidebar,body[data-template="neon"] .panel{background:#151a31eF;border-color:#414b78;color:var(--ink)}
  body[data-template="neon"] .history-card{background:#1e2542;border-color:#414b78}
  body[data-template="neon"] .history-card p,body[data-template="neon"] .desc,body[data-template="neon"] .panel-note,body[data-template="neon"] .status,body[data-template="neon"] .control-hint,body[data-template="neon"] .emotion-note{color:#aeb7ce}
  body[data-template="neon"] .field input,body[data-template="neon"] .field textarea,body[data-template="neon"] .field select{background:#10152b;color:#eef0fb;border-color:#414b78}
  body[data-template="neon"] .template-card{background:#1e2542;color:#eef0fb;border-color:#414b78}
  body[data-template="neon"] .template-card:hover{border-color:#e85aa5;background:#252d52}
  body[data-template="neon"] .template-card.active{border-color:#e85aa5}
  body[data-template="neon"] .template-desc{color:#aeb7ce}
  body[data-template="neon"] .template-tag{background:#2c345c;color:#dce2fb}
  body[data-template="neon"] .theme-button,body[data-template="neon"] .theme-popover{background:#151a31;color:#eef0fb;border-color:#414b78}
  body[data-template="neon"] .theme-option:hover,body[data-template="neon"] .theme-option.active{background:#2c345c}
  body[data-template="neon"] .theme-option small,body[data-template="neon"] .hot-template-label,body[data-template="neon"] .hot-template-config{color:#aeb7ce}
  body[data-template="neon"] .hot-template-card{background:#1b203b;color:#eef0fb;border-color:#414b78}
  body[data-template="neon"] .hot-template-text{color:#e7e9f2}
  body[data-template="neon"] .hot-template-tag{background:#2c345c;color:#dce2fb}
  body[data-template="neon"] .page-tab{background:#151a31;color:#aeb7ce;border-color:#414b78}
  body[data-template="neon"] .page-tab.active,body[data-template="neon"] .page-tab:hover{background:#e85aa5;color:#181326;border-color:#e85aa5}
  body[data-template="neon"] .advanced-seed{background:#151a31;border-color:#414b78}
  body[data-template="neon"] .mode-btn,body[data-template="neon"] .emotion-chip{background:#1e2542;color:#eef0fb;border-color:#414b78}
  body[data-template="neon"] .mode-btn.active,body[data-template="neon"] .mode-btn:hover,body[data-template="neon"] .emotion-chip.selected{background:#e85aa5;border-color:#e85aa5;color:#181326}
  body[data-template="neon"] .hero{background:radial-gradient(circle at 82% 10%,#e85aa555,transparent 33%),linear-gradient(135deg,#11152d,#242b58 56%,#432557)}
  body[data-template="neon"] .showcase-card{background:linear-gradient(145deg,#11152d,#242b58);border-color:#58659a}
  button,input,textarea,select{font:inherit}
  .app{display:grid;grid-template-columns:320px minmax(0,1fr);min-height:100vh}.sidebar{width:auto;padding:18px;background:rgba(255,253,248,.96);border-right:1px solid #dfc4b5;position:sticky;top:0;height:100vh;overflow:auto;z-index:5}
  .brand-mark{display:inline-flex;align-items:center;gap:8px;color:var(--plum);font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}.brand-dot{width:9px;height:9px;background:var(--rose);border-radius:50%;box-shadow:0 0 0 5px #c86f6122}.sidebar h1{font-size:22px;margin:10px 0 8px}.desc{color:var(--muted);font-size:14px;line-height:1.6}.sidebar-cta{display:block;text-align:center;text-decoration:none;margin:14px 0 20px}
  .history-heading{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:6px 0 10px}.history-heading h2{font-size:18px;margin:0}.history-heading span{font-size:12px;color:var(--muted);background:#f4e3d7;border-radius:999px;padding:4px 8px}.history-list{display:grid;gap:10px}.history-card{border:1px solid var(--card-bd);background:#fff8f0;border-radius:14px;padding:11px;min-width:0;box-shadow:0 6px 16px #5a37280d}.history-card strong{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:14px}.history-card small{display:block;color:var(--muted);font-size:12px;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.history-card audio{margin:7px 0 2px;height:32px}.history-card p{font-size:12px;line-height:1.45;color:#6e5554;margin:7px 0;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden;white-space:pre-wrap}.history-top{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:7px}.history-top time{font-size:11px;color:var(--muted)}.history-state{font-size:11px;font-weight:800;border-radius:999px;padding:3px 7px}.history-state.done{background:#e0f0e7;color:#367b64}.history-state.error{background:#f8dddd;color:#a5483d}.history-state.pending{background:#fff0c8;color:#956622}.history-load{border:0;background:transparent;color:#8b5548;padding:0;cursor:pointer;font-size:12px;font-weight:800}.history-load:hover{text-decoration:underline}.history-empty{border:1px dashed #ddc3b8;border-radius:14px;padding:14px;color:var(--muted);font-size:13px;line-height:1.5}.pending-card{border-color:#e2b27e;background:linear-gradient(135deg,#fff4d8,#fff8ef)}.pending-line{display:flex;align-items:center;gap:8px;font-weight:800;font-size:13px}.spinner{width:16px;height:16px;border:2px solid #e7c49d;border-top-color:#c86f61;border-radius:50%;animation:spin .8s linear infinite;flex:0 0 auto}.progress-track{height:5px;border-radius:99px;background:#ecd9ca;overflow:hidden;margin-top:10px}.progress-track span{display:block;width:42%;height:100%;border-radius:inherit;background:linear-gradient(90deg,#c86f61,#e6a06d,#c86f61);background-size:200% 100%;animation:progress 1.3s ease-in-out infinite}@keyframes spin{to{transform:rotate(360deg)}}@keyframes progress{0%{transform:translateX(-120%);background-position:0 0}100%{transform:translateX(260%);background-position:100% 0}}
  .template-wrap{max-width:1220px;margin:0 auto 24px}.template-intro{display:flex;align-items:end;justify-content:space-between;gap:14px;margin-bottom:11px}.template-intro h2{font-size:22px;margin:0}.template-intro p{margin:4px 0 0;color:var(--muted);font-size:13px}.template-status{font-size:12px;color:var(--muted);white-space:nowrap}.template-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.template-card{position:relative;display:flex;flex-direction:column;align-items:flex-start;gap:6px;min-width:0;text-align:left;border:1px solid var(--card-bd);border-radius:16px;padding:13px;background:rgba(255,253,249,.84);color:var(--ink);cursor:pointer;box-shadow:0 7px 20px #5a37280b;transition:transform .2s ease,border-color .2s ease,box-shadow .2s ease,background .2s ease}.template-card:hover{transform:translateY(-2px);border-color:var(--rose);box-shadow:0 10px 24px #5a37281c}.template-card.active{border:2px solid var(--rose);padding:12px;box-shadow:0 0 0 4px #c86f611c,0 10px 24px #5a37281c}.template-card-top{display:flex;align-items:center;justify-content:space-between;width:100%}.template-swatches{display:flex;gap:5px}.template-swatch{display:block;width:23px;height:23px;border-radius:50%;background:var(--swatch);border:2px solid #ffffffaa;box-shadow:0 1px 3px #0002}.template-check{display:none;width:21px;height:21px;align-items:center;justify-content:center;background:var(--rose);color:#fff;border-radius:50%;font-size:13px;font-weight:900}.template-card.active .template-check{display:inline-flex}.template-card strong{font-size:15px}.template-desc{color:var(--muted);font-size:12px;line-height:1.45;min-height:35px}.template-tags{display:flex;flex-wrap:wrap;gap:5px}.template-tag{font-size:10px;border-radius:999px;padding:3px 6px;background:#f4e3d7;color:#8b5548}
  .main-toolbar{max-width:1220px;margin:0 auto 12px;display:flex;justify-content:space-between;align-items:center;min-height:34px}.page-switch{display:flex;gap:6px}.page-tab{border:1px solid var(--card-bd);border-radius:999px;background:rgba(255,253,249,.9);color:var(--muted);padding:8px 12px;cursor:pointer;font-weight:800;font-size:12px}.page-tab.active,.page-tab:hover{background:var(--plum);border-color:var(--plum);color:#fff}.theme-menu{position:relative;z-index:8}.theme-button{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--card-bd);border-radius:999px;background:rgba(255,253,249,.9);color:var(--ink);padding:8px 12px;cursor:pointer;font-weight:800;box-shadow:0 5px 16px #5a37280b}.theme-button:hover{border-color:var(--rose)}.theme-button-dot{width:13px;height:13px;border-radius:50%;background:var(--rose);box-shadow:0 0 0 4px #c86f6122}.theme-button-caret{font-size:11px;color:var(--muted)}.theme-popover{position:absolute;right:0;top:calc(100% + 8px);width:242px;padding:8px;border:1px solid var(--card-bd);border-radius:16px;background:var(--paper);box-shadow:0 16px 36px #3d263126}.theme-option{width:100%;display:flex;align-items:center;gap:9px;border:0;border-radius:11px;background:transparent;color:var(--ink);padding:9px;cursor:pointer;text-align:left}.theme-option:hover,.theme-option.active{background:#f4e3d7}.theme-option .template-swatches{flex:0 0 auto}.theme-option strong,.theme-option small{display:block}.theme-option strong{font-size:13px}.theme-option small{font-size:11px;color:var(--muted);margin-top:2px}.theme-option-check{margin-left:auto;display:none;width:20px;height:20px;align-items:center;justify-content:center;background:var(--rose);color:#fff;border-radius:50%;font-size:12px;font-weight:900}.theme-option.active .theme-option-check{display:inline-flex}.hot-templates-wrap{max-width:1220px;margin:0 auto 24px}.hot-templates-intro{display:flex;justify-content:space-between;align-items:end;gap:14px;margin-bottom:11px}.hot-templates-intro h2{font-size:22px;margin:0}.hot-templates-intro p{margin:4px 0 0;color:var(--muted);font-size:13px}.hot-templates-hint{font-size:12px;color:var(--muted);white-space:nowrap}.hot-template-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.hot-template-card{display:flex;flex-direction:column;min-width:0;padding:15px;border:1px solid var(--card-bd);border-radius:18px;background:rgba(255,253,249,.88);box-shadow:0 8px 22px #5a37280c}.hot-template-top{display:flex;align-items:center;justify-content:space-between;gap:6px}.hot-template-kicker{font-size:11px;color:var(--rose);font-weight:900;letter-spacing:.05em}.hot-template-tags{display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end}.hot-template-tag{font-size:10px;border-radius:999px;padding:3px 6px;background:#f4e3d7;color:#8b5548}.hot-template-card h3{font-size:17px;line-height:1.35;margin:9px 0 2px}.hot-template-label{font-size:12px;color:var(--muted);margin:0}.hot-template-card audio{width:100%;height:32px;margin:7px 0}.hot-template-audio-missing{height:32px;display:flex;align-items:center;color:var(--muted);font-size:11px;border:1px dashed var(--card-bd);border-radius:9px;padding:0 8px;margin:7px 0}.hot-template-text{font-size:13px;line-height:1.6;color:var(--ink);margin:6px 0 8px;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:4;overflow:hidden;min-height:83px}.hot-template-config{font-size:11px;color:var(--muted);padding-top:7px;border-top:1px solid var(--card-bd);margin-top:auto}.hot-template-use{width:100%;margin-top:11px;font-size:12px}
  .main{padding:24px;min-width:0}h2{font-size:30px;margin:4px 0 6px}.open-folder{display:inline-block;margin:6px 0 2px;color:#7a4a30;font-weight:700;text-decoration:none}.open-folder:hover{text-decoration:underline}
  .hero{max-width:1220px;display:grid;grid-template-columns:minmax(0,1.3fr) minmax(270px,.7fr);gap:18px;margin:0 auto 20px;padding:28px;border-radius:26px;color:#fff7ed;background:radial-gradient(circle at 82% 10%,#d17b6455,transparent 32%),linear-gradient(135deg,#2b2135,#4b354d 55%,#74505a);box-shadow:0 18px 45px #4b354d2a;overflow:hidden}.hero-kicker{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#f4c29b;font-weight:800}.hero h1{font-size:clamp(32px,4.3vw,58px);line-height:1.05;margin:10px 0 14px;letter-spacing:-.03em}.hero p{max-width:680px;color:#ead8d2;line-height:1.75;margin:0}.hero-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:22px}.hero-actions a{display:inline-flex;align-items:center;padding:11px 15px;border-radius:999px;text-decoration:none;font-weight:800}.hero-primary{background:#f5bd9e;color:#3b2630}.hero-secondary{border:1px solid #f1c8b777;color:#fff7ed}.hero-proof{align-self:stretch;border-left:1px solid #f3cdb633;padding-left:22px;display:flex;flex-direction:column;justify-content:center;gap:12px}.hero-proof strong{font-size:30px;color:#fff}.hero-proof span{display:block;color:#dfc9c5;font-size:13px}.hero-proof .proof-line{display:flex;align-items:baseline;gap:8px}.hero-proof .proof-line strong{font-size:25px;color:#f4c29b}
  .studio-title{display:flex;justify-content:space-between;align-items:end;gap:14px;margin:24px auto 12px;max-width:1220px}.studio-title h2{margin:0}.studio-title p{margin:0;color:var(--muted);font-size:14px}.studio-grid{max-width:1220px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px;margin:0 auto 22px}.panel{background:rgba(255,253,249,.9);border:1px solid var(--card-bd);border-radius:20px;padding:18px;box-shadow:0 10px 28px #6a403018}.panel h3{margin:0 0 5px;font-size:21px}.panel-note{margin:0 0 14px;color:var(--muted);font-size:13px;line-height:1.6}.mode-switch{display:flex;gap:8px;margin:12px 0 14px}.mode-btn,.emotion-chip{border:1px solid #e1c4b9;background:#fff8f0;color:var(--ink);border-radius:999px;padding:8px 12px;cursor:pointer;font-weight:700}.mode-btn.active,.mode-btn:hover{background:var(--plum);border-color:var(--plum);color:#fff}.field{margin:11px 0}.field label{display:block;font-size:13px;font-weight:800;margin-bottom:6px}.field input,.field textarea,.field select{width:100%;border:1px solid #e0c7bd;border-radius:11px;background:#fffefa;color:var(--ink);padding:10px 11px;outline:none}.field input:focus,.field textarea:focus,.field select:focus{border-color:var(--rose);box-shadow:0 0 0 3px #c86f6122}.field textarea{min-height:86px;resize:vertical}.seed-file{border:1px dashed #d29d8f;padding:13px;border-radius:12px;background:#fff7f0}.primary-btn,.ghost-btn{border:0;border-radius:999px;padding:10px 15px;cursor:pointer;font-weight:800}.primary-btn{background:var(--rose);color:#fff}.primary-btn:hover{filter:brightness(1.06)}.ghost-btn{background:#f4e3d7;color:#6a4139}.ghost-btn:hover{background:#ecd0c1}.form-actions{display:flex;align-items:center;gap:10px;margin-top:14px}.status{font-size:13px;color:var(--muted);line-height:1.5}.status.error{color:#a5483d}.status.ok{color:#367b64}.hidden{display:none!important}
  .field-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.control-hint{font-size:11px;color:var(--muted);line-height:1.45;margin-top:4px;display:block}.advanced-seed{margin:8px 0;border:1px solid var(--card-bd);border-radius:12px;background:#fffaf5;padding:0 11px}.advanced-seed summary{cursor:pointer;color:var(--wood);font-size:13px;font-weight:800;padding:10px 0}.advanced-seed[open]{padding-bottom:2px}
  .seed-list{margin-top:16px;display:grid;gap:8px;max-height:250px;overflow:auto}.seed-card{display:flex;align-items:center;justify-content:space-between;gap:10px;border:1px solid #ead2c8;border-radius:12px;padding:10px;background:#fffaf5}.seed-card.active{border-color:var(--rose);box-shadow:0 0 0 3px #c86f6117}.seed-card strong{display:block;font-size:14px}.seed-card small{display:block;color:var(--muted);margin-top:3px}.seed-card audio{max-width:150px;margin:0}.seed-empty{border:1px dashed #ddc3b8;border-radius:12px;padding:14px;color:var(--muted);font-size:13px}
  .emotion-list{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 14px}.emotion-chip{font-size:13px}.emotion-chip.selected{background:#9e6659;border-color:#9e6659;color:#fff}.emotion-note{font-size:12px;color:var(--muted);margin:-5px 0 10px}.generation-result{margin-top:14px;border-radius:14px;background:#f8eee7;padding:12px}.generation-result audio{margin:0}.generation-result p{margin:8px 0 0;color:var(--muted);font-size:13px;line-height:1.5}.generation-progress{display:flex;align-items:center;gap:10px;padding:9px 11px;margin-top:12px;border-radius:11px;background:#fff2d7;color:#8b5b29;font-size:13px}.generation-progress .spinner{width:14px;height:14px}
  .showcase-wrap{max-width:1220px;margin:28px auto}.showcase-intro{display:flex;justify-content:space-between;align-items:end;gap:14px;margin-bottom:12px}.showcase-intro h2{margin:0}.showcase-intro p{margin:0;color:var(--muted);font-size:14px}.showcase-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.showcase-card{background:linear-gradient(145deg,#2c2434,#4b354d);color:#fff8ee;border:1px solid #896273;border-radius:18px;padding:16px;box-shadow:0 12px 28px #4b354d25}.showcase-kicker{color:#f0b99d;font-size:11px;font-weight:800;letter-spacing:.08em}.showcase-card h3{font-size:20px;line-height:1.35;margin:8px 0 2px}.showcase-label{color:#dfc8c0;font-size:13px;margin:0 0 8px}.showcase-card .tag.warm{background:#a86c5e;color:#fff1e9}.showcase-card audio{width:100%;margin:8px 0}.showcase-text{white-space:pre-wrap;color:#e5d2cc;font-size:13px;line-height:1.65;min-height:120px}.showcase-card .ghost-btn{background:#f1c2a4;color:#402832}.showcase-card .ghost-btn:hover{background:#ffd4b6}
  .char-block{margin-top:22px}.char-block h3{font-size:22px;border-left:4px solid var(--wood);padding-left:10px;margin:10px 0}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px}.card{background:var(--card);border:1px solid var(--card-bd);border-radius:16px;padding:14px;box-shadow:0 8px 22px #5a372814;min-width:0}.card-head{display:flex;align-items:center;gap:8px;min-width:0}.card-head b{background:var(--wood);color:#fff;border-radius:999px;padding:4px 8px;font-size:13px;max-width:56%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:0 1 auto}.card-head h3{margin:0;font-size:18px;min-width:0;overflow-wrap:anywhere;flex:1}.meta{color:var(--muted);font-size:13px;margin:7px 0 6px}.tags{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}.tag{background:#f7dfd2;border-radius:999px;padding:4px 8px;font-size:12px}.tag.tiny{padding:3px 6px;font-size:11px}.text,.desc{font-size:14px;line-height:1.6;overflow-wrap:anywhere}.desc{color:#6f4e43}audio{width:100%;margin-top:8px}.warn{color:#ad4e3d;font-size:13px}.footer{max-width:1220px;margin:28px auto;color:var(--muted);font-size:13px}
  @media (max-width:1050px){.hero{grid-template-columns:1fr}.hero-proof{border-left:0;border-top:1px solid #f3cdb633;padding:14px 0 0;display:grid;grid-template-columns:repeat(3,1fr)}}
  @media (max-width:950px){.app{display:flex;flex-direction:column}.sidebar{position:relative;width:auto;height:auto;max-height:none}.history-list{grid-template-columns:repeat(auto-fill,minmax(230px,1fr));max-height:none}.studio-grid{grid-template-columns:1fr}.showcase-grid{grid-template-columns:1fr 1fr}.hot-template-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
  @media (max-width:620px){.main{padding:14px}.hero{padding:20px;border-radius:20px}.hero-proof{display:flex}.showcase-grid{grid-template-columns:1fr}.studio-title{display:block}.studio-title p{margin-top:5px}.field-row{grid-template-columns:1fr}.hot-templates-intro{display:block}.hot-templates-hint{display:block;margin-top:6px}.hot-template-grid{grid-template-columns:1fr}.theme-popover{right:-4px}.theme-button{font-size:12px}}
"""

    studio_html = f"""
      <div class="main-toolbar"><div class="page-switch" role="tablist" aria-label="工作站頁面"><button type="button" class="page-tab active" data-page="workspace" role="tab" aria-selected="true">聲音工作台</button><button type="button" class="page-tab" data-page="templates" role="tab" aria-selected="false">熱門模板</button></div><div class="theme-menu"><button type="button" class="theme-button" id="theme-button" aria-expanded="false"><span class="theme-button-dot"></span><span id="theme-button-label">主題配色</span><span class="theme-button-caret">⌄</span></button><div class="theme-popover" id="theme-popover" hidden>{theme_options_html}</div></div></div>
      <section class="hero workspace-view" aria-labelledby="hero-title">
        <div>
          <div class="hero-kicker">VOICE SEED STUDIO · LOCAL PRODUCTION TOOL</div>
          <h1 id="hero-title">把聲音做成<br>可以反覆使用的角色資產</h1>
          <p>用一句文字設計聲線，或上傳一段參考音檔建立聲音種子。之後選擇種子與複合情緒，直接生成能上戲、能追溯、能重複使用的角色語音。</p>
          <div class="hero-actions"><a class="hero-primary" href="#hot-templates" data-page-link="templates">選熱門模板</a><a class="hero-secondary" href="#studio">開始建立聲音種子</a></div>
        </div>
        <div class="hero-proof"><div class="proof-line"><strong>{total_samples}</strong><span>已驗證語音樣本</span></div><div class="proof-line"><strong>9</strong><span>預置音色與預設別名</span></div><div class="proof-line"><strong>Clone</strong><span>固定參考聲音，保留表演控制</span></div></div>
      </section>
      <section class="hot-templates-wrap templates-view hidden" id="hot-templates" aria-labelledby="hot-templates-title"><div class="hot-templates-intro"><div><h2 id="hot-templates-title">熱門模板</h2><p>熱門台詞與完整情緒配置已配好；只要選擇聲音種子，就能直接套用並生成。</p></div><span class="hot-templates-hint">選模板 → 鎖定種子 → 立即生成</span></div><div class="hot-template-grid">{hot_templates_html}</div></section>
      <div class="studio-title workspace-view" id="studio"><div><h2>聲音種子工作台</h2><p>先建立一個固定聲音，再到熱門模板直接套用。</p></div></div>
      <section class="studio-grid workspace-view" aria-label="聲音種子與語音生成">
        <article class="panel">
          <h3>① 建立聲音種子</h3><p class="panel-note">文字設計適合創作新角色；上傳音檔適合固定真人或既有角色聲線。參考音檔僅保存在本機 outputs/voice_seeds。</p>
          <div class="mode-switch"><button type="button" class="mode-btn active" data-mode="text_design">文字設計</button><button type="button" class="mode-btn" data-mode="audio_clone">上傳音檔</button></div>
          <form id="seed-form">
            <div class="field-row"><div class="field"><label for="seed-name">種子名稱</label><input id="seed-name" required placeholder="例如：沈霜｜冷面攝政王"></div><div class="field"><label for="seed-gender">性別鎖定</label><select id="seed-gender"><option value="中性／不指定">中性／不指定</option><option value="女性">女性（硬性）</option><option value="男性">男性（硬性）</option></select></div></div>
            <div id="text-seed-fields"><div class="field"><label for="seed-description">聲音描述</label><textarea id="seed-description" placeholder="例如：甜美清亮、自然有笑意的年輕女性，不要幼稚或低沉。"></textarea></div></div>
            <details class="advanced-seed" id="advanced-seed-settings"><summary>進階設定：試音台詞與參考音檔</summary><div class="field"><label for="seed-reference-text">建立種子時的試音台詞</label><textarea id="seed-reference-text">你好，這是我的固定聲音種子。從今天開始，請記住我的語氣與節奏。</textarea></div><div id="audio-seed-fields" class="hidden"><div class="field"><label for="seed-file">WAV / MP3 參考音檔</label><input id="seed-file" class="seed-file" type="file" accept=".wav,.mp3,audio/wav,audio/mpeg"><small class="status">官方限制：WAV/MP3，Base64 不超過 10 MB。</small></div></div></details>
            <div class="form-actions"><button class="primary-btn" type="submit">建立並保存種子</button><span id="seed-status" class="status">尚未建立種子</span></div>
          </form>
          <div id="seed-list" class="seed-list"><div class="seed-empty">建立後的聲音種子會出現在這裡。</div></div>
        </article>
        <article class="panel">
          <h3>② 指定種子生成情緒語音</h3><p class="panel-note">每次生成都鎖定同一參考音檔，再疊加複合情緒；結果會記錄 seed hash，方便重生與追查。</p>
          <form id="generation-form"><div class="field"><label for="seed-select">聲音種子</label><select id="seed-select"><option value="">請先建立或載入種子</option></select></div><div class="field"><label>複合情緒（可多選，最多 5 個）</label><div id="emotion-list" class="emotion-list">{emotion_chips}</div><p class="emotion-note">可混合基礎情緒與複合情緒，模型會依序做情緒轉場；順序越前優先度越高。</p></div><div class="field-row"><div class="field"><label for="intensity-select">情緒強度</label><select id="intensity-select"><option>自然</option><option>克制</option><option>明顯</option><option>強烈但不破音</option></select></div><div class="field"><label for="delivery-select">演繹方式</label><select id="delivery-select"><option>電影對白</option><option>古裝台詞</option><option>內心獨白</option><option>旁白敘事</option><option>低語耳語</option><option>舞台宣告</option><option>質問逼問</option><option>安撫哄勸</option></select></div></div><div class="field-row"><div class="field"><label for="pace-select">語速節奏</label><select id="pace-select"><option value="慢速">慢速（留白多）</option><option value="標準" selected>標準（自然）</option><option value="快速">快速（緊迫）</option><option value="忽快忽慢">忽快忽慢（情緒轉場）</option></select></div><div class="field"><label for="pitch-select">音高走向</label><select id="pitch-select"><option>自然</option><option>偏低沉</option><option>偏明亮</option><option>先低後高</option><option>先高後低</option></select></div></div><div class="field-row"><div class="field"><label for="pause-select">停頓策略</label><select id="pause-select"><option>自然停頓</option><option>短停頓</option><option>長停頓</option><option>句尾留白</option><option>斷續哽咽</option></select></div><div class="field"><label for="ending-select">收句方式</label><select id="ending-select"><option>完整收句</option><option>尾音放輕</option><option>欲言又止</option><option>情緒停住但不截斷</option></select></div></div><div class="field"><label for="performance-note">導演補充（可選）</label><input id="performance-note" placeholder="例如：前半壓住怒火，最後一句放柔，保留一拍呼吸。"><small class="control-hint">這段會和性別鎖定、聲音種子一起送給模型，只控制表演，不改寫音色。</small></div><div class="field"><label for="generation-text">台詞</label><textarea id="generation-text" required>你以為我今日來，是要聽你替自己辯解？三年前你跪在雪裡求我救他，我替你擋下那一刀。</textarea></div><div class="form-actions"><button class="primary-btn" type="submit">生成帶情緒的語音</button><span id="generation-status" class="status">等待聲音種子</span></div><div id="generation-progress" class="generation-progress hidden"><span class="spinner"></span><span>正在生成中，正在鎖定聲音種子與表演指令…</span></div></form>
          <div id="generation-result" class="generation-result hidden"><audio id="generated-audio" controls></audio><p id="generation-meta"></p></div>
        </article>
      </section>
    """

    script_html = """
    <script>
    const $ = selector => document.querySelector(selector);
    let seedMode = 'text_design';
    let seedCache = [];
    const apiAvailable = location.protocol === 'http:' || location.protocol === 'https:';
    const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
    const showPage = page => {
      const templates = page === 'templates';
      document.querySelectorAll('.workspace-view').forEach(node => node.classList.toggle('hidden', templates));
      document.querySelectorAll('.templates-view').forEach(node => node.classList.toggle('hidden', !templates));
      document.querySelectorAll('.page-tab').forEach(tab => { const active = tab.dataset.page === page; tab.classList.toggle('active', active); tab.setAttribute('aria-selected', active ? 'true' : 'false'); });
      if (templates) window.scrollTo({top:0, behavior:'smooth'});
    };
    document.querySelectorAll('.page-tab').forEach(tab => tab.addEventListener('click', () => showPage(tab.dataset.page)));
    document.querySelectorAll('[data-page-link]').forEach(link => link.addEventListener('click', event => { event.preventDefault(); showPage(link.dataset.pageLink); document.querySelector(link.getAttribute('href'))?.scrollIntoView({behavior:'smooth'}); }));
    const templateNames = { ancient:'古裝月影', cinema:'電影暗幕', daylight:'清透日光', neon:'霓虹聲場' };
    const applyTemplate = (id, persist=true) => {
      const template = Object.prototype.hasOwnProperty.call(templateNames, id) ? id : 'ancient';
      document.body.dataset.template = template;
      document.querySelectorAll('.theme-option').forEach(card => {
        const active = card.dataset.template === template;
        card.classList.toggle('active', active);
        card.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      const label = $('#theme-button-label');
      if (label) label.textContent = templateNames[template];
      if (persist) { try { localStorage.setItem('voice-studio-template', template); } catch (_) {} }
    };
    const themeButton = $('#theme-button');
    const themePopover = $('#theme-popover');
    themeButton?.addEventListener('click', event => { event.stopPropagation(); const open = themePopover?.hasAttribute('hidden'); if (open) themePopover?.removeAttribute('hidden'); else themePopover?.setAttribute('hidden',''); themeButton.setAttribute('aria-expanded', open ? 'true' : 'false'); });
    document.querySelectorAll('.theme-option').forEach(option => option.addEventListener('click', () => { applyTemplate(option.dataset.template); themePopover?.setAttribute('hidden',''); themeButton?.setAttribute('aria-expanded','false'); }));
    document.addEventListener('click', event => { if (!event.target.closest('.theme-menu')) { themePopover?.setAttribute('hidden',''); themeButton?.setAttribute('aria-expanded','false'); } });
    let savedTemplate = 'ancient';
    try { savedTemplate = localStorage.getItem('voice-studio-template') || 'ancient'; } catch (_) {}
    applyTemplate(savedTemplate, false);
    const setStatus = (selector, message, type='') => { const node = $(selector); if (!node) return; node.textContent = message; node.className = `status ${type}`; };
    if ($('#seed-description')) $('#seed-description').required = true;
    const readDataUrl = file => new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(new Error('讀取音檔失敗')); reader.readAsDataURL(file); });
    const historyList = $('#history-list');
    const historyCount = $('#history-count');
    const updateHistoryCount = () => { if (historyCount && historyList) historyCount.textContent = `${historyList.querySelectorAll('.history-card:not(.pending-card)').length} 筆`; };
    const historyCard = (result, text, emotions, options, seedLabel) => {
      const tags = (emotions || []).slice(0, 4).map(item => `<span class="tag tiny">${escapeHtml(item)}</span>`).join('');
      const label = (emotions || []).join('、') || '平靜';
      const duration = Number.isFinite(Number(result.durationSeconds)) ? ` · ${Number(result.durationSeconds).toFixed(2)}s` : '';
      return `<article class="history-card" data-history-id="${escapeHtml(result.id)}"><div class="history-top"><span class="history-state done">已完成</span><time>剛剛</time></div><strong>${escapeHtml(seedLabel || '聲音種子')}</strong><small>${escapeHtml(result.gender || '不指定')} · ${escapeHtml(label)} · ${escapeHtml(options.pace || '標準')}${duration}</small><div class="tags">${tags}</div><audio controls preload="none" src="${escapeHtml(result.url)}"></audio><p>${escapeHtml(text)}</p><button type="button" class="history-load" data-history-text="${escapeHtml(text, true)}">帶入台詞</button></article>`;
    };
    const addPendingHistory = (seedLabel) => {
      if (!historyList) return null;
      $('#history-empty')?.remove();
      const id = `pending-${Date.now()}`;
      historyList.insertAdjacentHTML('afterbegin', `<article class="history-card pending-card" id="${id}"><div class="history-top"><span class="history-state pending">生成中</span><time>現在</time></div><div class="pending-line"><span class="spinner"></span><span>正在生成中…</span></div><small>${escapeHtml(seedLabel || '聲音種子')} · 正在鎖定聲線與表演指令</small><div class="progress-track"><span></span></div></article>`);
      updateHistoryCount();
      return id;
    };
    const finishPendingHistory = (id, result, text, emotions, options, seedLabel, error) => {
      const pending = id && document.getElementById(id);
      if (!pending || !historyList) return;
      if (error){ pending.className = 'history-card'; pending.innerHTML = `<div class="history-top"><span class="history-state error">生成失敗</span><time>剛剛</time></div><strong>${escapeHtml(seedLabel || '聲音種子')}</strong><small>${escapeHtml(error)}</small>`; updateHistoryCount(); return; }
      pending.outerHTML = historyCard(result, text, emotions, options, seedLabel); updateHistoryCount();
      while (historyList.querySelectorAll('.history-card').length > 30) historyList.lastElementChild?.remove();
    };
    historyList?.addEventListener('click', event => { const button = event.target.closest('.history-load'); if (!button) return; $('#generation-text').value = button.dataset.historyText || ''; $('#studio')?.scrollIntoView({behavior:'smooth'}); setStatus('#generation-status','歷史台詞已載入；可調整表演選項後重生','ok'); });

    function renderSeeds(){
      const select = $('#seed-select');
      const list = $('#seed-list');
      if (!select || !list) return;
      if (!seedCache.length){ select.innerHTML = '<option value="">請先建立或載入種子</option>'; list.innerHTML = '<div class="seed-empty">建立後的聲音種子會出現在這裡。</div>'; setStatus('#generation-status','等待聲音種子'); return; }
      const selected = select.value;
      select.innerHTML = '<option value="">請選擇聲音種子</option>' + seedCache.map(seed => `<option value="${escapeHtml(seed.id)}">${escapeHtml(seed.name)} · ${escapeHtml(seed.gender || '不指定')} · ${escapeHtml(seed.kind === 'text_design' ? '文字設計' : '上傳音檔')}</option>`).join('');
      if (seedCache.some(seed => seed.id === selected)) select.value = selected;
      list.innerHTML = seedCache.map(seed => `<div class="seed-card ${seed.id === select.value ? 'active' : ''}" data-seed-card="${escapeHtml(seed.id)}"><div><strong>${escapeHtml(seed.name)}</strong><small>${escapeHtml(seed.gender || '不指定')} · ${escapeHtml(seed.kind === 'text_design' ? '文字設計' : '上傳音檔')} · ${escapeHtml((seed.referenceSha256 || '').slice(0,12))}</small></div><audio controls preload="none" src="${escapeHtml(seed.audioUrl)}"></audio></div>`).join('');
      setStatus('#generation-status', select.value ? '已鎖定聲音種子' : '請選擇聲音種子', select.value ? 'ok' : '');
    }
    async function loadSeeds(){
      if (!apiAvailable){ setStatus('#seed-status','請用 run_dashboard.py 啟動本機工作站', 'error'); return; }
      try { const response = await fetch('/api/seeds'); const data = await response.json(); if (!response.ok) throw new Error(data.error || '無法讀取種子'); seedCache = data.seeds || []; renderSeeds(); } catch (error){ setStatus('#seed-status', error.message, 'error'); }
    }
    document.querySelectorAll('.mode-btn').forEach(button => button.addEventListener('click', () => { seedMode = button.dataset.mode; document.querySelectorAll('.mode-btn').forEach(item => item.classList.toggle('active', item === button)); $('#text-seed-fields').classList.toggle('hidden', seedMode !== 'text_design'); $('#audio-seed-fields').classList.toggle('hidden', seedMode !== 'audio_clone'); const description = $('#seed-description'); if (description) description.required = seedMode === 'text_design'; const advanced = $('#advanced-seed-settings'); if (advanced) advanced.open = true; }));
    $('#seed-select')?.addEventListener('change', renderSeeds);
    $('#seed-form')?.addEventListener('submit', async event => {
      event.preventDefault();
      if (!apiAvailable){ setStatus('#seed-status','請用 run_dashboard.py 啟動本機工作站', 'error'); return; }
      const button = event.submitter; button.disabled = true; setStatus('#seed-status', seedMode === 'text_design' ? '正在設計固定聲線…' : '正在保存參考音檔…');
      try {
        const body = { kind: seedMode, name: $('#seed-name').value.trim(), gender: $('#seed-gender').value, description: $('#seed-description')?.value.trim() || '', referenceText: $('#seed-reference-text')?.value.trim() || '' };
        if (seedMode === 'audio_clone'){ const file = $('#seed-file').files[0]; if (!file) throw new Error('請選擇 WAV 或 MP3'); body.dataUrl = await readDataUrl(file); }
        const response = await fetch('/api/seeds', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
        const data = await response.json(); if (!response.ok) throw new Error(data.error || '建立種子失敗');
        setStatus('#seed-status', `已建立：${data.seed.name} · ${data.seed.gender || '不指定'}`, 'ok'); $('#seed-form').reset(); $('#seed-gender').value = '中性／不指定'; seedMode = 'text_design'; $('#seed-description').required = true; document.querySelectorAll('.mode-btn').forEach(item => item.classList.toggle('active', item.dataset.mode === seedMode)); $('#text-seed-fields').classList.remove('hidden'); $('#audio-seed-fields').classList.add('hidden'); await loadSeeds(); $('#seed-select').value = data.seed.id; renderSeeds();
      } catch (error){ setStatus('#seed-status', error.message, 'error'); } finally { button.disabled = false; }
    });
    document.querySelectorAll('.emotion-chip').forEach(chip => chip.addEventListener('click', () => { chip.classList.toggle('selected'); if ($('#generation-form')) $('#generation-form').dataset.emotionOrder = ''; }));
    const applyHotTemplate = button => {
      showPage('workspace');
      const emotions = (button.dataset.emotions || '').split('|').filter(Boolean);
      $('#generation-text').value = button.dataset.text || '';
      if ($('#generation-form')) $('#generation-form').dataset.emotionOrder = JSON.stringify(emotions);
      document.querySelectorAll('.emotion-chip').forEach(chip => chip.classList.toggle('selected', emotions.includes(chip.dataset.emotion)));
      [['#intensity-select','intensity'],['#delivery-select','delivery'],['#pace-select','pace'],['#pitch-select','pitch'],['#pause-select','pause'],['#ending-select','ending']].forEach(([selector,key]) => { const field=$(selector); if (field && button.dataset[key]) field.value = button.dataset[key]; });
      $('#performance-note').value = button.dataset.note || '';
      const hasSeed = Boolean($('#seed-select')?.value);
      setStatus('#generation-status', hasSeed ? '模板已套用，正在送出生成…' : '模板已套用，請先選擇聲音種子', hasSeed ? 'ok' : '');
      $('#studio')?.scrollIntoView({behavior:'smooth'});
      if (hasSeed) window.setTimeout(() => $('#generation-form')?.requestSubmit(), 0);
    };
    document.querySelectorAll('.hot-template-use').forEach(button => button.addEventListener('click', () => applyHotTemplate(button)));
    $('#generation-form')?.addEventListener('submit', async event => {
      event.preventDefault();
      if (!apiAvailable){ setStatus('#generation-status','請用 run_dashboard.py 啟動本機工作站', 'error'); return; }
      const seedId = $('#seed-select').value; if (!seedId) { setStatus('#generation-status','請先選擇聲音種子', 'error'); return; }
      const seed = seedCache.find(item => item.id === seedId);
      let emotions = [...document.querySelectorAll('.emotion-chip.selected')].map(chip => chip.dataset.emotion);
      try { const templateOrder = JSON.parse($('#generation-form').dataset.emotionOrder || '[]'); if (Array.isArray(templateOrder)) emotions = [...templateOrder.filter(item => emotions.includes(item)), ...emotions.filter(item => !templateOrder.includes(item))]; } catch (_) {}
      emotions = emotions.slice(0, 5);
      const options = { intensity:$('#intensity-select').value, delivery:$('#delivery-select').value, pace:$('#pace-select').value, pitch:$('#pitch-select').value, pause:$('#pause-select').value, ending:$('#ending-select').value, performanceNote:$('#performance-note').value.trim() };
      const text = $('#generation-text').value.trim();
      const button = event.submitter || $('#generation-form button[type="submit"]'); button.disabled = true; $('#generation-progress')?.classList.remove('hidden'); setStatus('#generation-status','正在鎖定聲線並生成…');
      const pendingId = addPendingHistory(seed?.name);
      try { const response = await fetch('/api/generate', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ seedId, emotions, text, ...options }) }); const data = await response.json(); if (!response.ok) throw new Error(data.error || '生成失敗'); const result = data.generation; $('#generated-audio').src = result.url + `?t=${Date.now()}`; $('#generation-result').classList.remove('hidden'); $('#generation-meta').textContent = `已生成 · ${result.gender || '不指定'} · ${result.emotions.join('、') || '平靜'} · ${result.delivery || options.delivery} · ${result.pace || options.pace} · ${Number(result.durationSeconds || 0).toFixed(2)}s${result.durationLimited ? ' · 已套用短台詞長度護欄' : ''} · seed hash ${(result.seedSha256 || '').slice(0,12)} · voice-clone`; finishPendingHistory(pendingId, result, text, emotions, options, seed?.name); setStatus('#generation-status','生成完成，可直接播放或繼續改表演選項重生', 'ok'); } catch (error){ finishPendingHistory(pendingId, null, text, emotions, options, seed?.name, error.message); setStatus('#generation-status', error.message, 'error'); } finally { button.disabled = false; $('#generation-progress')?.classList.add('hidden'); }
    });
    document.querySelectorAll('.showcase-load').forEach(button => button.addEventListener('click', () => { $('#generation-text').value = button.dataset.text; document.querySelector('#studio').scrollIntoView({behavior:'smooth'}); setStatus('#generation-status','示範台詞已載入；請選擇種子與表演選項後生成', 'ok'); }));
    loadSeeds();
  </script>
"""

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='14' fill='%23c86f61'/%3E%3C/svg%3E"/>
<title>Voice Seed Studio｜聲音種子工作站</title>
<style>
{style_html}
</style>
</head>
<body data-template="ancient">
  <div class="app">
    <aside class="sidebar">
      <div class="brand-mark"><span class="brand-dot"></span> Voice Seed Studio</div>
      <h1>聲音種子工作站</h1>
      <p class="desc">建立固定聲線、疊加複合情緒，再把成品交給角色對白或短劇製作。左側只保留生成成品，工作台與熱門模板在主區上方切換。</p>
      <a class="ghost-btn sidebar-cta" href="#studio">＋ 建立新種子</a>
      <div class="history-heading"><h2>生成紀錄</h2><span id="history-count">{len(history_samples)} 筆</span></div>
      <p class="desc" style="font-size:12px;margin-top:-4px">生成中會顯示即時動畫；完成後可播放、帶回台詞再生成。</p>
      <div id="history-list" class="history-list">{history_html}</div>
    </aside>
    <main class="main">
      {studio_html}
      <div class="footer">Generated at: {html.escape(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'))} · 本機 Voice Seed Studio</div>
    </main>
  </div>
{script_html}
</body>
</html>"""


def collect_tests(outputs_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not outputs_root.exists():
        return items
    for test_dir in sorted(outputs_root.iterdir(), key=lambda p: p.name):
        if not test_dir.is_dir() or test_dir.name.startswith("."):
            continue
        if test_dir.name not in VISIBLE_TESTS:
            continue
        manifest_path = test_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(manifest, dict):
            continue

        samples = manifest.get("samples", [])
        if not isinstance(samples, list):
            samples = []

        generated_at = parse_time(manifest.get("generatedAt"))
        items.append(
            {
                "id": test_dir.name,
                "title": safe_text(
                    manifest.get("galleryTitle")
                    or manifest.get("title")
                    or test_dir.name,
                    test_dir.name,
                ),
                "subtitle": safe_text(
                    manifest.get("gallerySubtitle")
                    or manifest.get("subtitle")
                    or "",
                ),
                "candidateCount": int(manifest.get("candidateCount", len(samples) or 0)),
                "generatedCount": int(manifest.get("generatedCount", len(samples) or 0)),
                "generatedAt": generated_at.isoformat(),
                "urlPrefix": str(test_dir.name),
                "groups": safe_group(samples),
            }
        )

    items.sort(key=lambda item: item["generatedAt"], reverse=True)
    return items


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    outputs_root = (args.outputs_root or (project_root / "outputs")).resolve()
    output_path = (args.output or (outputs_root / "index.html")).resolve()
    tests = collect_tests(outputs_root)
    if not tests:
        print(f"No valid manifests found in {outputs_root}")
        return 0

    html = render_dashboard(tests, outputs_root=outputs_root)
    atomic_write(output_path, html)
    print(f"Dashboard generated: {output_path} (tests={len(tests)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
