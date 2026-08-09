#!/usr/bin/env python3
"""Curated ancient-Chinese recitation and original background-music recipes.

The catalogue contains performance direction, not extra spoken content.  Public-
domain verse is used only as editable starter copy.  Built-in music is generated
locally by this project so an audio scene never depends on an unlicensed track.
"""

from __future__ import annotations

from typing import Any


RECITATION_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "frontier-vow",
        "name": "塞外壯行",
        "kicker": "豪情不是吼，是眼前真的有萬里山河",
        "text": "千里黃雲白日曛，北風吹雁雪紛紛。\n莫愁前路無知己，天下誰人不識君。",
        "emotions": ["蒼茫", "沉著", "豪情", "送別的暖意"],
        "intensity": "明顯",
        "pace": "忽快忽慢",
        "pitch": "自然起伏",
        "pause": "句尾留白",
        "ending": "完整收句",
        "anchorModes": ["authority", "narration", "neutral"],
        "lineDirections": [
            "先看見風雪與天色，聲音向遠處送，不急著立英雄姿態",
            "北風加重但咬字仍穩；句尾只停，不做制式下墜",
            "轉身看向故人，音量收近，豪氣下面要有惜別",
            "不是口號；帶笑與篤定向前推，最後乾淨落地",
        ],
        "note": "胸腔有力量但不喊麥；由遠景收到近景，再把最後一句送出去。",
        "defaultBgm": "frontier-drums",
        "defaultRoom": "open-air",
    },
    {
        "id": "mountain-rain",
        "name": "山水空明",
        "kicker": "像在景中忽然明白一件事，不是朗誦比賽",
        "text": "空山新雨後，天氣晚來秋。\n明月松間照，清泉石上流。",
        "emotions": ["清寂", "欣然", "看見", "釋然"],
        "intensity": "克制",
        "pace": "慢速",
        "pitch": "自然起伏",
        "pause": "長停頓",
        "ending": "尾音放輕",
        "anchorModes": ["narration", "intimate", "neutral"],
        "lineDirections": [
            "第一個字前先吸入雨後涼意；空，不等於虛弱",
            "從鼻息裡帶出秋意，句尾平收，讓畫面繼續",
            "明月出現時亮一點，重音在『照』之前自然形成",
            "水流是動的，節奏微微向前；最後放輕音量而非壓低音高",
        ],
        "note": "留白比拖尾重要；每句是一個新發現，四句不能唱成同一條曲線。",
        "defaultBgm": "mountain-qin",
        "defaultRoom": "stone-pavilion",
    },
    {
        "id": "night-rain-letter",
        "name": "夜雨寄情",
        "kicker": "克制思念，真正的情緒藏在不敢多說",
        "text": "君問歸期未有期，巴山夜雨漲秋池。\n何當共剪西窗燭，卻話巴山夜雨時。",
        "emotions": ["被問住", "惆悵", "想像中的溫暖", "含笑的思念"],
        "intensity": "克制",
        "pace": "慢速",
        "pitch": "自然起伏",
        "pause": "句尾留白",
        "ending": "情緒停住但不截斷",
        "anchorModes": ["intimate", "narration", "neutral"],
        "lineDirections": [
            "像讀到對方來信後被問住；第一個『期』不故作悲傷",
            "雨聲讓空間變深，『漲』字只是看見，不必加戲",
            "想到未來同坐窗邊，氣息回暖，語速自然快半步",
            "帶一點笑意回看此刻；結尾懸住思念，不拉成哭腔",
        ],
        "note": "整段只允許一次明顯轉暖；不能每句都用低沉尾音表示古風。",
        "defaultBgm": "moon-window",
        "defaultRoom": "warm-study",
    },
    {
        "id": "palace-decision",
        "name": "宮闈決斷",
        "kicker": "權力場裡越安靜，越要讓人聽見刀鋒",
        "text": "你們要的答案，朕今日便給。\n功過寫在史冊，忠奸留待後人；可這座城裡的百姓，等不到後人。",
        "emotions": ["審視", "冷靜威壓", "短暫自責", "決斷"],
        "intensity": "明顯",
        "pace": "忽快忽慢",
        "pitch": "偏低沉",
        "pause": "長停頓",
        "ending": "完整收句",
        "anchorModes": ["authority", "emotional", "neutral"],
        "lineDirections": [
            "先看完殿上每一個人再開口；『答案』不需大聲",
            "前半逐字清楚，分號後責任落回自己；最後一句向前，不拖尾",
        ],
        "note": "權威來自判斷，不來自壓低喉頭；保留一瞬間的人味，再做決定。",
        "defaultBgm": "palace-undertow",
        "defaultRoom": "great-hall",
    },
    {
        "id": "river-memory",
        "name": "江上懷人",
        "kicker": "有時間走過的重量，但不把每一句都念老",
        "text": "故人入我夢，明我長相憶。\n君今在羅網，何以有羽翼。",
        "emotions": ["驚覺", "思念", "擔憂", "無能為力"],
        "intensity": "克制",
        "pace": "標準",
        "pitch": "自然起伏",
        "pause": "斷續哽咽",
        "ending": "欲言又止",
        "anchorModes": ["intimate", "emotional", "narration"],
        "lineDirections": [
            "夢中忽然認出故人，先是驚，不要一開始就悲",
            "明白對方也記得自己，短暫得到安慰",
            "醒來後現實回來；『羅網』壓住但不做戲劇腔",
            "是真的在問，尾端保留等待感，不准用標準陳述下降",
        ],
        "note": "情緒順序是認出、靠近、失去、追問；四句各有不同的句尾功能。",
        "defaultBgm": "moon-window",
        "defaultRoom": "warm-study",
    },
]


BGM_PRESETS: list[dict[str, Any]] = [
    {
        "id": "mountain-qin",
        "name": "山水琴音",
        "description": "疏朗五聲音階、風感底色；適合山水與釋然。",
        "mood": "空靈",
        "color": "#6d8f83",
        "generator": "mountain",
    },
    {
        "id": "moon-window",
        "name": "月窗慢弦",
        "description": "近距離撥弦與暖色長音；適合思念、夜讀與含蓄告白。",
        "mood": "溫暖惆悵",
        "color": "#8a6c91",
        "generator": "moon",
    },
    {
        "id": "frontier-drums",
        "name": "塞外戰鼓",
        "description": "克制低鼓與開闊長音；保留豪氣但不搶台詞。",
        "mood": "蒼茫豪情",
        "color": "#a56845",
        "generator": "frontier",
    },
    {
        "id": "palace-undertow",
        "name": "宮闈暗潮",
        "description": "低頻暗流與稀疏金屬音；適合權謀、決斷與壓迫。",
        "mood": "冷峻懸疑",
        "color": "#584f67",
        "generator": "palace",
    },
    {
        "id": "none",
        "name": "純人聲",
        "description": "不加入配樂，只保留人聲與選定空間。",
        "mood": "乾淨",
        "color": "#777777",
        "generator": None,
    },
]


ROOM_PRESETS: list[dict[str, Any]] = [
    {"id": "dry", "name": "錄音棚乾聲", "description": "零空間效果，便於後續剪輯。"},
    {"id": "warm-study", "name": "暖書房", "description": "很短的木質反射，近而有人味。"},
    {"id": "stone-pavilion", "name": "石亭", "description": "清楚的早期反射，帶少量空氣感。"},
    {"id": "great-hall", "name": "大殿", "description": "較深但克制，不做廉價山洞回聲。"},
    {"id": "open-air", "name": "曠野", "description": "幾乎無室內尾響，只保留遠景寬度。"},
]


def get_recitation_template(template_id: str) -> dict[str, Any] | None:
    return next((dict(item) for item in RECITATION_TEMPLATES if item["id"] == str(template_id)), None)


def get_bgm_preset(preset_id: str) -> dict[str, Any] | None:
    return next((dict(item) for item in BGM_PRESETS if item["id"] == str(preset_id)), None)


def get_room_preset(preset_id: str) -> dict[str, Any] | None:
    return next((dict(item) for item in ROOM_PRESETS if item["id"] == str(preset_id)), None)


def performance_direction(template_id: str, text: str) -> tuple[str, dict[str, Any]]:
    """Return a line-aware acting score that is never sent as spoken text."""
    template = get_recitation_template(template_id)
    if not template:
        raise ValueError("找不到指定古人說詞模板")
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    if not lines:
        raise ValueError("說詞內容不能為空")
    directions = template["lineDirections"]
    score = []
    for index, line in enumerate(lines[:12]):
        direction = directions[min(index, len(directions) - 1)]
        score.append(f"第{index + 1}句「{line[:34]}」：{direction}")
    prompt = (
        "古人說詞模式：這不是朗誦比賽、古風廣告或播音示範，而是一個人在具體時刻真的看見、想起、"
        "判斷或告別。使用現代觀眾能感受到的自然中文節奏，古意來自語義與氣息，不來自統一壓低喉頭、"
        "拖長尾音或每句下墜。整段先形成念頭再出聲；換行是情緒節拍，不是機械停頓。"
        f"情緒弧線：{' → '.join(template['emotions'])}。逐句表演譜：{'；'.join(score)}。"
        f"總導演要求：{template['note']} 只說台詞本身一次；不得朗讀情緒、序號、引號或導演指令，"
        "不得自行補詩名、作者、旁白、解釋或尾聲。"
    )
    metadata = {
        "templateId": template["id"],
        "templateName": template["name"],
        "emotions": list(template["emotions"]),
        "lineDirections": list(template["lineDirections"]),
        "lineCount": len(lines),
    }
    return prompt, metadata
