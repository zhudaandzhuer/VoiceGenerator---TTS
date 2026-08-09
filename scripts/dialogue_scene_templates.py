"""Original two-character scenes for production-ready dialogue generation.

Every turn is deliberately short enough to be regenerated independently.  The
role's objective, subtext, listening cue, emotional colour and pause belong to
the acting brief; only ``text`` (or its trusted ``taggedText`` twin) is spoken.
"""

from __future__ import annotations

from typing import Any


DIALOGUE_SCENES: list[dict[str, Any]] = [
    {
        "id": "rain-platform-choice",
        "title": "末班月台｜留下還是放手",
        "format": "電視劇",
        "genre": "現代愛情",
        "hook": "列車進站前四十秒，分手三年的兩個人終於說到真正的原因。",
        "circumstance": "大雨封路，末班車已經進站，兩人沒有時間再繞圈子。",
        "relationship": "曾經同居、因誤會分開三年的舊情人",
        "shotScale": "電視劇近景",
        "takeStyle": "生活流",
        "roles": {
            "A": {"name": "程野", "gender": "男性", "objective": "確認她是否還願意相信自己", "subtext": "我不是來解釋，我是來帶妳回家。"},
            "B": {"name": "林晚", "gender": "女性", "objective": "逼他第一次把選擇說明白", "subtext": "只要你敢留下，我就敢再信一次。"},
        },
        "turns": [
            {"role": "B", "text": "車到了。你若只是來道歉，現在已經說完了。", "taggedText": "（克制，故作平靜）車到了。你若只是來道歉，現在已經說完了。", "emotion": "克制的委屈", "direction": "先看列車再看他；像替對方找台階，其實在等挽留。", "listen": "聽見他叫住自己後才回頭。", "pauseAfter": 0.55},
            {"role": "A", "text": "我不是來道歉。我把工作辭了，房子也退了。", "taggedText": "（呼吸略急，直接）我不是來道歉。[短暫停頓]我把工作辭了，房子也退了。", "emotion": "緊張中的決心", "direction": "前句阻止她離開；後句給事實，不賣慘。", "listen": "看見她不相信，立刻交出籌碼。", "pauseAfter": 0.7},
            {"role": "B", "text": "你每次都替我決定。那這一次呢，你要去哪裡？", "taggedText": "（壓住動情）你每次都替我決定。[沉默片刻]那這一次呢，你要去哪裡？", "emotion": "怨氣轉忐忑", "direction": "第一句是舊傷；問句放輕上揚，真的需要答案。", "listen": "聽懂他已經放棄原本生活，防線開始鬆。", "pauseAfter": 0.62},
            {"role": "A", "text": "妳去哪裡，我就去哪裡。這次換妳決定。", "taggedText": "（很輕，篤定）妳去哪裡，我就去哪裡。[深呼吸]這次換妳決定。", "emotion": "釋然與動情", "direction": "不是宣誓；像終於把控制權交還給她，最後平收。", "listen": "等她問完才真正明白該說什麼。", "pauseAfter": 0.9},
        ],
    },
    {
        "id": "palace-poison-cup",
        "title": "毒酒入殿｜君臣最後一問",
        "format": "電視劇",
        "genre": "古裝權謀",
        "hook": "一杯毒酒擺在殿前，皇帝與功臣都知道這不是在審案。",
        "circumstance": "深夜空殿，禁軍守住殿門，桌上只有偽造書信與一杯毒酒。",
        "relationship": "少年相識、如今互不敢信的君王與重臣",
        "shotScale": "電影近景",
        "takeStyle": "古裝含蓄",
        "roles": {
            "A": {"name": "蕭承", "gender": "男性", "objective": "逼臣子親口交代，給自己一個不殺他的理由", "subtext": "只要你求一次，我就讓你活。"},
            "B": {"name": "顧衡", "gender": "男性", "objective": "讓君王承認這是恐懼，不是國法", "subtext": "死可以，但別把我們的舊情也寫成罪。"},
        },
        "turns": [
            {"role": "A", "text": "書信、私印、證人都在。顧衡，你還有什麼要說？", "taggedText": "（威嚴，疲憊）書信、私印、證人都在。[短暫停頓]顧衡，你還有什麼要說？", "emotion": "壓抑的憤怒", "direction": "不是宣判，是最後一次暗示對方辯解；名字說得私人。", "listen": "等他抬頭才問最後一句。", "pauseAfter": 0.75},
            {"role": "B", "text": "臣只想知道，陛下信的是證據，還是終於等到一個疑我的理由？", "taggedText": "（守禮，悲憤）臣只想知道，陛下信的是證據，還是……終於等到一個疑我的理由？", "emotion": "克制的悲憤", "direction": "行禮但不求饒；真正刺中的是「終於」。", "listen": "聽出皇帝仍在等自己低頭，反而站直。", "pauseAfter": 0.8},
            {"role": "A", "text": "朕若不疑你，明日死的就是天下人。", "taggedText": "（低聲，動搖）朕若不疑你，明日死的就是天下人。", "emotion": "動搖與自我說服", "direction": "越說越輕；像對自己解釋，不能喊成帝王宣言。", "listen": "被「終於」刺中，先避開視線。", "pauseAfter": 0.7},
            {"role": "B", "text": "那臣飲酒。只是十五年前城樓上的那句信我，請陛下別忘得太乾淨。", "taggedText": "（釋然，帶舊情）那臣飲酒。[沉默片刻]只是十五年前城樓上的那句信我，請陛下……別忘得太乾淨。", "emotion": "釋然中的悲傷", "direction": "先接受死亡；後句不控訴，只把共同記憶放回桌上。", "listen": "聽出皇帝已無法回頭，所以自己先結束審判。", "pauseAfter": 1.0},
        ],
    },
    {
        "id": "interrogation-birthday",
        "title": "審訊破口｜生日蠟燭沒有點",
        "format": "電影",
        "genre": "犯罪懸疑",
        "hook": "刑警不用證據施壓，只提起嫌疑人女兒桌上沒點燃的蠟燭。",
        "circumstance": "凌晨三點，嫌疑人已重複同一份口供四次，錄音機仍在轉。",
        "relationship": "老練刑警與以沉默保護同夥的父親",
        "shotScale": "電影特寫",
        "takeStyle": "克制真實",
        "roles": {
            "A": {"name": "陳警官", "gender": "中性／不指定", "objective": "讓對方主動說出共犯位置", "subtext": "我知道你不是為自己沉默。"},
            "B": {"name": "周凱", "gender": "男性", "objective": "守住口供，也守住女兒不被牽連", "subtext": "別拿我女兒逼我。"},
        },
        "turns": [
            {"role": "A", "text": "你說十點就回家。可桌上的蛋糕沒切，蠟燭也沒點。", "taggedText": "（平靜，精確）你說十點就回家。可桌上的蛋糕沒切，蠟燭也沒點。", "emotion": "平靜施壓", "direction": "像核對物證；提蛋糕時不要煽情。", "listen": "看見他手指第一次收緊，才補後句。", "pauseAfter": 0.6},
            {"role": "B", "text": "堵車。孩子等累了，睡著很正常。", "taggedText": "（防備，急著合理化）堵車。孩子等累了，睡著很正常。", "emotion": "防備與心虛", "direction": "第一句過快；後句努力恢復平穩，露出準備過的口供感。", "listen": "聽到女兒被提起，立刻搶答。", "pauseAfter": 0.42},
            {"role": "A", "text": "她沒睡。她一直坐到十二點，問你是不是不要她了。", "taggedText": "（放輕，不指責）她沒睡。[沉默片刻]她一直坐到十二點，問你是不是不要她了。", "emotion": "同理中的逼問", "direction": "放下審訊腔；最後問句是轉述孩子，不模仿童聲。", "listen": "等他的藉口說完，不追，改從父親身份進入。", "pauseAfter": 0.85},
            {"role": "B", "text": "……南碼頭，十二號倉。他們答應過，不碰我家裡人。", "taggedText": "[深呼吸]（崩開，低聲）南碼頭，十二號倉。[短暫停頓]他們答應過，不碰我家裡人。", "emotion": "崩潰後的恐懼", "direction": "先認輸，再意識到自己也被騙；不要哭喊。", "listen": "孩子的原話擊穿防線，沉默一拍才開口。", "pauseAfter": 0.95},
        ],
    },
    {
        "id": "emergency-consent",
        "title": "急診抉擇｜簽字前的十秒",
        "format": "電視劇",
        "genre": "醫療職人",
        "hook": "手術同意書只差簽名，醫師必須把風險說清楚，也讓家屬能做決定。",
        "circumstance": "急診走廊，手術室正在等，病患血壓持續下降。",
        "relationship": "主治醫師與突然必須替父親決定的女兒",
        "shotScale": "電視劇近景",
        "takeStyle": "職人寫實",
        "roles": {
            "A": {"name": "許醫師", "gender": "女性", "objective": "讓家屬理解風險並作出自己的選擇", "subtext": "我不能替妳保證，但我會替他撐到底。"},
            "B": {"name": "雅文", "gender": "女性", "objective": "從醫師口中得到一個能承受後果的答案", "subtext": "如果我簽錯了，我一輩子都不會原諒自己。"},
        },
        "turns": [
            {"role": "A", "text": "現在手術有風險，不手術，他可能撐不過今晚。", "taggedText": "（專業，清楚）現在手術有風險；不手術，他可能撐不過今晚。", "emotion": "疲憊但穩定", "direction": "資訊先行，不把家屬推向任何答案。", "listen": "確認她看著自己，才說第二個選項。", "pauseAfter": 0.55},
            {"role": "B", "text": "你別跟我說可能。你告訴我，如果是你爸爸，你簽不簽？", "taggedText": "（慌亂，帶怒）你別跟我說可能。[急促呼吸]你告訴我，如果是你爸爸，你簽不簽？", "emotion": "恐懼轉質問", "direction": "怒氣是為了逃離選擇；最後一句真的在求助。", "listen": "風險兩字讓她失去抓手，搶著打斷。", "pauseAfter": 0.65},
            {"role": "A", "text": "我不能替你簽。但我可以告訴你，進去以後，我會把他當成我爸爸救。", "taggedText": "（溫柔，堅定）我不能替你簽。[短暫停頓]但我可以告訴你，進去以後，我會把他當成我爸爸救。", "emotion": "溫柔與決心", "direction": "先守住界線；後句不是保證結果，是承諾全力。", "listen": "接住她的私人提問，但不冒充家屬做決定。", "pauseAfter": 0.8},
            {"role": "B", "text": "好。我簽。你帶他回來。", "taggedText": "[深呼吸]（仍害怕，決定了）好。我簽。[短暫停頓]你帶他回來。", "emotion": "恐懼中的決絕", "direction": "不是命令醫師保證；像把父親交到對方手裡。", "listen": "聽見承諾後才找到可以承擔的理由。", "pauseAfter": 0.9},
        ],
    },
    {
        "id": "roommate-pudding-trial",
        "title": "布丁審判｜真正的嫌疑人",
        "format": "電視劇",
        "genre": "生活喜劇",
        "hook": "凌晨一點的合租屋，為了一顆布丁召開了毫無必要的刑偵大會。",
        "circumstance": "全屋被叫到客廳，冰箱門貼著手繪案情圖。",
        "relationship": "熟到會互相拆台的兩位合租室友",
        "shotScale": "電視劇中景",
        "takeStyle": "喜劇節拍",
        "roles": {
            "A": {"name": "小孟", "gender": "女性", "objective": "逼偷吃布丁的人認罪", "subtext": "至少認真對待我貼在冰箱上的名字。"},
            "B": {"name": "阿哲", "gender": "男性", "objective": "結束鬧劇並讓她想起真相", "subtext": "我有錄影，但我想看妳能演到哪裡。"},
        },
        "turns": [
            {"role": "A", "text": "我再問一次，誰動了第二層、貼我名字、畫了三個骷髏頭的布丁？", "taggedText": "（一本正經，節奏快）我再問一次，誰動了第二層、貼我名字、畫了三個骷髏頭的布丁？", "emotion": "誇張的憤怒", "direction": "把小事當重案；細節越認真越好笑，不要刻意搞笑聲。", "listen": "確定對方坐好才正式開庭。", "pauseAfter": 0.45},
            {"role": "B", "text": "請問受害者，昨晚十二點四十三分人在何處？", "taggedText": "（配合演出，故作冷靜）請問受害者，昨晚十二點四十三分人在何處？", "emotion": "壓住笑意", "direction": "故意進入刑警節奏，問完等她自己跳坑。", "listen": "先忍住笑，認真翻開不存在的筆錄。", "pauseAfter": 0.48},
            {"role": "A", "text": "我在沙發上看劇。這跟我的布丁有什麼關係？", "taggedText": "（理直氣壯，開始心虛）我在沙發上看劇。[短暫停頓]這跟我的布丁有什麼關係？", "emotion": "得意轉疑惑", "direction": "前句像完美不在場證明；後句語速放慢，開始想起來。", "listen": "對時間太精確感到不安，但仍撐住。", "pauseAfter": 0.5},
            {"role": "B", "text": "關係就是，你邊看邊吃，還叫我替你拿湯匙。證物在群組影片裡。", "taggedText": "（平靜補刀，最後輕笑）關係就是，你邊看邊吃，還叫我替你拿湯匙。[輕笑]證物在群組影片裡。", "emotion": "得意與輕笑", "direction": "前三個字落槌；最後像展示決定性證物，笑點後留白。", "listen": "等她問完才翻轉主導權。", "pauseAfter": 0.9},
        ],
    },
    {
        "id": "orbit-last-reply",
        "title": "延遲十一分鐘｜最後一次回覆",
        "format": "電影",
        "genre": "科幻劇情",
        "hook": "訊號往返要二十二分鐘，但艙內氧氣只剩九分鐘。",
        "circumstance": "失控太空艙與地面控制中心只能靠延遲語音通話。",
        "relationship": "任務指揮官與留在地面的丈夫",
        "shotScale": "電影特寫",
        "takeStyle": "克制真實",
        "roles": {
            "A": {"name": "周嵐", "gender": "女性", "objective": "讓丈夫相信自己仍有時間，免去他的自責", "subtext": "你聽見時，我已經不在了。"},
            "B": {"name": "江明", "gender": "男性", "objective": "讓她停止保護自己，說出真正想說的話", "subtext": "我知道救援來不及，但我想陪妳走完。"},
        },
        "turns": [
            {"role": "B", "text": "救援軌道已經算出來了。妳再等二十分鐘，我們一定接得到妳。", "taggedText": "（努力穩住，說給自己相信）救援軌道已經算出來了。妳再等二十分鐘，我們一定接得到妳。", "emotion": "恐懼中的希望", "direction": "技術詞說清楚；「一定」是自己也不信的保證。", "listen": "這是十一分鐘前她仍有氧氣時發出的回覆。", "pauseAfter": 0.72},
            {"role": "A", "text": "我剛從舷窗看見海岸線。今天的地球，很漂亮。", "taggedText": "（呼吸略短，溫柔）我剛從舷窗看見海岸線。[喘息]今天的地球，很漂亮。", "emotion": "疲憊與釋然", "direction": "不回應救援時間；用眼前景色替他準備告別。", "listen": "聽見他仍在計算，選擇先說一件日常的事。", "pauseAfter": 0.75},
            {"role": "B", "text": "周嵐，別再報平安了。妳想說什麼，就說吧。我在聽。", "taggedText": "（崩開一點，仍溫柔）周嵐，別再報平安了。[深呼吸]妳想說什麼，就說吧。我在聽。", "emotion": "悲傷與接納", "direction": "第一次叫全名；不是催告別，是允許她停止堅強。", "listen": "終於聽懂她在描述最後看見的畫面。", "pauseAfter": 0.85},
            {"role": "A", "text": "那你替我把陽台的花搬進去。還有，今晚別關燈。讓我遠遠看著家。", "taggedText": "（動情，帶一點笑）那你替我把陽台的花搬進去。還有……[沉默片刻]今晚別關燈。讓我遠遠看著家。", "emotion": "動情與告別", "direction": "前句仍是生活交代；最後不是哭腔，像找到回家的方向。", "listen": "得到允許後才把真正的告別說出口。", "pauseAfter": 1.1},
        ],
    },
]


def get_dialogue_scene(scene_id: str) -> dict[str, Any] | None:
    """Return a scene by id without accepting untrusted user-authored metadata."""
    return next((scene for scene in DIALOGUE_SCENES if scene["id"] == scene_id), None)
