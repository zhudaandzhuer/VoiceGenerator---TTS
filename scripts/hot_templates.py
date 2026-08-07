"""Curated voice-template definitions shared by the dashboard and generator.

The template itself is deterministic metadata: a line, a performance recipe,
and a voice-seed profile. Generated audio is stored separately in
``outputs/hot_templates/manifest.json`` so the UI never presents a template
without an auditable take.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


THEME_TEMPLATES = [
    {"id": "ancient", "name": "古裝月影", "swatches": ["#2b2135", "#c86f61", "#f1b89f"]},
    {"id": "cinema", "name": "電影暗幕", "swatches": ["#171923", "#d66b52", "#f2c078"]},
    {"id": "daylight", "name": "清透日光", "swatches": ["#f6f1e8", "#4b9b91", "#e4a15d"]},
    {"id": "neon", "name": "霓虹聲場", "swatches": ["#11152d", "#e85aa5", "#52d5cf"]},
]


HOT_TEMPLATES = [
    {
        "id": "regent-confession",
        "title": "冷面攝政王｜壓抑的愧疚 → 釋然",
        "label": "古裝權謀 · 一句就能上戲",
        "text": "你以為本王今日來，是要聽你替自己辯解？三年前你跪在雪裡求我救他，我替你擋下那一刀……不是因為你。是因為我不願看你，再為任何人低頭。",
        "emotions": ["壓抑的憤怒", "愧疚", "釋然"],
        "intensity": "明顯", "delivery": "古裝台詞", "pace": "忽快忽慢", "pitch": "先低後高", "pause": "句尾留白", "ending": "情緒停住但不截斷",
        "note": "前半壓住怒火，第二句帶一點哽咽，最後一句放柔。",
        "tags": ["熱門", "權謀", "情緒轉場"],
        "seed_name": "模板聲種｜冷面攝政王",
        "seed_gender": "男性",
        "seed_description": "成年男性，古裝權臣聲線，低沉醇厚、冷靜克制，近距離說話，字尾收得乾淨；不要蒼老，不要沙啞過度。",
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
        "seed_name": "模板聲種｜戰場女將軍",
        "seed_gender": "女性",
        "seed_description": "成年女性，女將軍聲線，明亮而有力量，胸腔共鳴清楚，能壓住哭腔與怒意；不要男性低沉共鳴。",
    },
    {
        "id": "sweet-confession",
        "title": "甜美心動｜害羞 → 喜悅 → 撒嬌",
        "label": "甜美少女聲 · 戀愛告白",
        "text": "你怎麼又來了呀？我才沒有一直等你……只是剛好把喜歡你的話，練習了三十七遍。那現在可以換你抱我一下嗎？",
        "emotions": ["忐忑", "喜悅", "溫柔"],
        "intensity": "自然", "delivery": "電影對白", "pace": "標準", "pitch": "偏明亮", "pause": "短停頓", "ending": "尾音放輕",
        "note": "甜而不嗲，笑意放在聲音裡，最後一句像撒嬌但字要清楚。",
        "tags": ["甜美", "戀愛", "高人氣"],
        "seed_name": "模板聲種｜甜美少女",
        "seed_gender": "女性",
        "seed_description": "年輕女性，甜美清亮、自然有笑意，像戀愛劇女主角，輕柔但不幼稚，咬字清楚，不要低沉。",
    },
    {
        "id": "loli-adventure",
        "title": "蘿莉冒險｜興奮 → 得意 → 撒嬌",
        "label": "蘿莉活潑聲 · 角色台詞",
        "text": "笨蛋，這點小事才難不倒我！看好了，我只要數到三，這扇門就會自己打開。……喂，你快點誇我，不然我就要把寶物藏起來了！",
        "emotions": ["喜悅", "驚訝", "得意"],
        "intensity": "明顯", "delivery": "舞台宣告", "pace": "快速", "pitch": "偏明亮", "pause": "短停頓", "ending": "完整收句",
        "note": "童聲感來自輕快與高位置，不要尖銳刺耳；每句保持可懂。",
        "tags": ["蘿莉音", "活潑", "角色扮演"],
        "seed_name": "模板聲種｜蘿莉冒險家",
        "seed_gender": "女性",
        "seed_description": "二次元蘿莉角色聲線，年幼感、活潑明亮、音高偏高但不刺耳，帶淘氣笑意，咬字清楚；不要成熟御姐聲。",
    },
    {
        "id": "onee-sama-command",
        "title": "御姐宣告｜冷靜 → 壓迫 → 溫柔",
        "label": "御姐強勢聲 · 反差收句",
        "text": "站到我身後，現在不是逞強的時候。誰敢越過這條線，我就讓他知道代價。至於你……乖一點，剩下的交給我。",
        "emotions": ["決絕", "憤怒", "溫柔"],
        "intensity": "明顯", "delivery": "舞台宣告", "pace": "標準", "pitch": "偏低沉", "pause": "句尾留白", "ending": "尾音放輕",
        "note": "前兩句壓迫感要穩，最後一句收成只對一個人說的溫柔。",
        "tags": ["御姐音", "強勢", "反差"],
        "seed_name": "模板聲種｜御姐指揮官",
        "seed_gender": "女性",
        "seed_description": "成年女性，御姐指揮官聲線，低沉有磁性、穩定強勢、吐字俐落；可以在最後一句切換成貼近耳邊的溫柔，不要男性音色。",
    },
    {
        "id": "healing-sister",
        "title": "溫柔姐姐｜心疼 → 安撫 → 釋然",
        "label": "治癒系姐姐聲 · 深夜陪伴",
        "text": "今天已經很努力了，剩下的明天再想。先把眼睛閉上，慢慢呼吸，我會在這裡陪你。你不用立刻變好，聽見了嗎？",
        "emotions": ["悲傷", "溫柔", "欣慰"],
        "intensity": "克制", "delivery": "安撫哄勸", "pace": "慢速", "pitch": "偏低沉", "pause": "長停頓", "ending": "完整收句",
        "note": "像深夜通話的可靠姐姐，溫柔但不虛弱，句尾不要拖長。",
        "tags": ["治癒", "姐姐音", "安撫"],
        "seed_name": "模板聲種｜治癒系姐姐",
        "seed_gender": "女性",
        "seed_description": "成年女性，溫柔可靠的姐姐聲，暖、穩、帶一點氣聲，像深夜陪伴與安撫，不要幼稚或過度甜膩。",
    },
    {
        "id": "hotblooded-boy",
        "title": "少年熱血｜不甘 → 勇氣 → 宣戰",
        "label": "少年男聲 · 動畫戰鬥宣言",
        "text": "我輸過一次，不代表我會一直輸！把名字記好了，下一次站在你面前的人，會是已經超越昨天的我。這場比賽，我接下了！",
        "emotions": ["憤怒", "決絕", "喜悅"],
        "intensity": "強烈但不破音", "delivery": "舞台宣告", "pace": "快速", "pitch": "偏明亮", "pause": "短停頓", "ending": "完整收句",
        "note": "少年感來自向前的明亮共鳴，熱血但不要嘶吼破音。",
        "tags": ["少年音", "熱血", "動畫"],
        "seed_name": "模板聲種｜熱血少年",
        "seed_gender": "男性",
        "seed_description": "年輕男性，少年動畫主角聲線，明亮有衝勁、帶青春感，音高不過低，熱血但不嘶吼破音。",
    },
    {
        "id": "mystery-vow",
        "title": "懸疑誓言｜恐懼 → 忐忑 → 決絕",
        "label": "低語耳語 · 最後一字要落地",
        "text": "門外那個人，不是我哥。你現在離開還來得及，別回頭，也別問我為什麼知道。若天亮以前我沒有出去，就把這段錄音交給警察。",
        "emotions": ["恐懼", "忐忑", "決絕"],
        "intensity": "強烈但不破音", "delivery": "低語耳語", "pace": "標準", "pitch": "偏低沉", "pause": "斷續哽咽", "ending": "完整收句",
        "note": "貼近麥克風的壓低聲線，恐懼藏在呼吸裡，最後一句清楚收住。",
        "tags": ["懸疑", "低語", "反轉"],
        "seed_name": "模板聲種｜懸疑低語",
        "seed_gender": "女性",
        "seed_description": "成年女性，近距離懸疑低語聲線，氣聲與恐懼藏在呼吸裡，字詞清楚，最後能轉為決絕；不要男性低沉。",
    },
    {
        "id": "soulful-neighbor",
        "title": "鄰家暖光｜自然 → 心疼 → 安心",
        "label": "清透鄰家聲 · 像真人在你身邊說話",
        "text": "你不用急著回答，我只是想讓你知道，這裡一直有人替你留著燈。累了就先坐一下，等你準備好了，我們再慢慢往前走。",
        "emotions": ["溫柔", "悲傷", "欣慰"],
        "intensity": "克制", "delivery": "電影對白", "pace": "標準", "pitch": "自然", "pause": "自然停頓", "ending": "尾音放輕",
        "note": "像熟悉的人坐在身旁說話，保留自然呼吸與小小停頓，不要播音腔。",
        "tags": ["靈性", "鄰家", "有溫度"],
        "seed_name": "模板聲種｜鄰家暖光",
        "seed_gender": "女性",
        "seed_description": "成年女性，清透自然的鄰家聲，像真人在同一個房間輕聲交談；保留自然呼吸、微小停頓與笑意，不要播音腔或機械等重音。",
    },
    {
        "id": "warm-confidant",
        "title": "可靠知己｜無奈 → 心疼 → 釋然",
        "label": "溫暖男聲 · 深夜談心",
        "text": "我知道你不是不難過，只是不想讓別人看見。沒關係，在我這裡不用裝得很勇敢。今天先把自己抱好，明天醒來再決定要去哪裡。",
        "emotions": ["無奈", "溫柔", "釋然"],
        "intensity": "克制", "delivery": "安撫哄勸", "pace": "慢速", "pitch": "偏低沉", "pause": "長停頓", "ending": "完整收句",
        "note": "真實、近距離、帶一點氣息摩擦；不要完美對稱的句子節奏。",
        "tags": ["靈性", "知己", "暖男聲"],
        "seed_name": "模板聲種｜可靠知己",
        "seed_gender": "男性",
        "seed_description": "成年男性，溫暖可靠的知己聲，低沉但不厚重，近距離自然說話，保留呼吸與細微不規則停頓；不要客服播報感。",
    },
    {
        "id": "lazy-magnetic",
        "title": "慵懶磁性｜厭倦 → 欲言又止 → 溫柔",
        "label": "慵懶磁性聲 · 低聲情話",
        "text": "別催，我又不會消失。只是今天有點累，想聽你再叫我一次名字。嗯，就這樣……靠近一點，我想把你的聲音記久一點。",
        "emotions": ["厭倦", "欲言又止", "溫柔"],
        "intensity": "克制", "delivery": "低語耳語", "pace": "慢速", "pitch": "偏低沉", "pause": "長停頓", "ending": "尾音放輕",
        "note": "慵懶不是含糊，字要完整；句尾帶一點笑意和未說完的餘韻。",
        "tags": ["磁性", "慵懶", "情話"],
        "seed_name": "模板聲種｜慵懶磁性",
        "seed_gender": "男性",
        "seed_description": "成年男性，慵懶磁性的近距離聲線，低沉、鬆弛、帶一點笑意與氣聲；咬字仍要清楚，不要機械拖長。",
    },
    {
        "id": "spiritual-whisper",
        "title": "月光低語｜悲傷 → 釋然 → 溫柔",
        "label": "靈性低語聲 · 像把秘密交給夜色",
        "text": "有些答案不是找不到，只是要等心安靜下來。你聽，風已經替我們把那句再見說完了。從今天起，請帶著祝福走，不必再回頭。",
        "emotions": ["悲傷", "釋然", "溫柔"],
        "intensity": "克制", "delivery": "內心獨白", "pace": "慢速", "pitch": "偏明亮", "pause": "長停頓", "ending": "情緒停住但不截斷",
        "note": "空氣感與靈性來自留白、呼吸和輕微共鳴變化，不要朗誦腔。",
        "tags": ["靈性", "月光", "療癒"],
        "seed_name": "模板聲種｜月光低語",
        "seed_gender": "女性",
        "seed_description": "成年女性，空靈但真實的月光低語聲，氣息柔和、共鳴靠前，像在夜裡把秘密交給一個人；不要冰冷合成感。",
    },
    {
        "id": "podcast-warmth",
        "title": "溫暖旁白｜平靜 → 共感 → 希望",
        "label": "知性旁白聲 · 有呼吸的故事感",
        "text": "我們常常以為，人生要先準備好才能出發。後來才明白，真正的勇氣，是一邊害怕，一邊替自己留一盞小燈。那盞燈，就是你還願意相信明天。",
        "emotions": ["平靜", "欣慰", "釋然"],
        "intensity": "自然", "delivery": "旁白敘事", "pace": "標準", "pitch": "自然", "pause": "自然停頓", "ending": "完整收句",
        "note": "像優質 podcast 的真人主持，不要每句同一個節拍；重點字自然加深。",
        "tags": ["旁白", "知性", "希望"],
        "seed_name": "模板聲種｜溫暖旁白",
        "seed_gender": "女性",
        "seed_description": "成年女性，知性溫暖的 podcast 主持聲，清楚但不播音，保留真人呼吸、自然重音與句間微變化，讓故事有陪伴感。",
    },
    {
        "id": "old-soul-storyteller",
        "title": "老靈魂說書｜滄桑 → 幽默 → 溫柔",
        "label": "故事老人聲 · 一開口就有記憶",
        "text": "那年冬天比現在冷得多，可人心啊，總比天氣更會捉弄人。老頭子我走了半輩子，最後才懂，真正值得帶走的，從來不是金子，是有人記得你笑過。",
        "emotions": ["悲傷", "欣慰", "溫柔"],
        "intensity": "自然", "delivery": "旁白敘事", "pace": "慢速", "pitch": "偏低沉", "pause": "長停頓", "ending": "尾音放輕",
        "note": "帶年歲但不要沙啞到聽不清，偶爾有一點笑意和生活感。",
        "tags": ["老靈魂", "說書", "記憶"],
        "seed_name": "模板聲種｜老靈魂說書人",
        "seed_gender": "男性",
        "seed_description": "中年偏成熟男性，老靈魂說書人聲線，有歲月感但咬字清楚，帶自然笑意與呼吸，不要刻意老化或機械低沉。",
    },
    {
        "id": "soft-lover",
        "title": "軟聲戀人｜忐忑 → 喜悅 → 依戀",
        "label": "甜軟戀人聲 · 近距離告白",
        "text": "我其實沒有那麼勇敢，只是每次看見你，就覺得可以再試一次。你不要笑我，好不好？我是真的很喜歡你，喜歡到想把每一個明天都分給你。",
        "emotions": ["忐忑", "喜悅", "溫柔"],
        "intensity": "自然", "delivery": "電影對白", "pace": "慢速", "pitch": "偏明亮", "pause": "短停頓", "ending": "完整收句",
        "note": "像真人鼓起勇氣告白，保留吞嚥、呼吸與小小停頓，不要甜到失真。",
        "tags": ["甜軟", "戀人", "真實感"],
        "seed_name": "模板聲種｜軟聲戀人",
        "seed_gender": "女性",
        "seed_description": "年輕女性，甜軟但真實的戀人聲，近距離、帶羞怯呼吸與自然笑意；不要幼稚、不要機械撒嬌、每字清楚。",
    },
]


def load_hot_templates(outputs_root: Path | None = None) -> list[dict[str, Any]]:
    """Merge generated audio metadata into the curated template definitions."""
    templates = [dict(item) for item in HOT_TEMPLATES]
    manifest_path = outputs_root / "hot_templates" / "manifest.json" if outputs_root else None
    if not manifest_path or not manifest_path.exists():
        return templates
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return templates
    generated = {str(item.get("id")): item for item in manifest.get("templates", []) if isinstance(item, dict)}
    for template in templates:
        audio = generated.get(template["id"])
        if audio:
            template.update(audio)
    return templates
