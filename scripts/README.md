# VoiceGenerator - TTS（小米 MiMo）獨立語音工作區

這個資料夾只保留 `scripts/` 與 `outputs/` 兩層目錄（你指定的結構）。
語音能力完整沿用既有流程：  
- `generate_casting_samples.py`：針對角色產生試音樣本  
- `generate_voice_gallery.py`：候選聲線批次產生 + README/index.html 對照
- `generate_tts_catalog.py`：依官方清單依序生成預置音色、基礎/複合情緒、語調、音色定位、人設方言與句內音頻標籤（可續跑）
- `generate_showcase.py`：生成首頁古裝劇複合情緒示範音檔
- `generate_hot_templates.py`：建立熱門模板專用聲音種子，批次生成並保存每張模板的 WAV
- `cinema_templates.py`：14 組原創電影／電視劇配音場景，包含人物目的、阻力、潛台詞與三段表演節拍
- `voice_studio_server.py`：本機 Voice Seed Studio API（文字建種、上傳建種、固定種子 + 情緒生成）
- `test_cinema_pipeline.py`：影視模板、標籤隔離與非法覆寫回退的離線測試
- `verify_voice_take.py`：用 MiMo ASR 驗收最新成品是否念出控制字、重複或偏離台詞
- `build_dialogue_voice_profile.py`：從遊戲對話 JSON 組出 production profile（可選）  
- `generate_production_dialogue.py`：依照 profile 批次生成正式對白 WAV + manifest  
- `providers/mimo.py`：MiMo API adapter（`chat/completions`）

預設 profile 檔案放在 `scripts/profiles/`，你可以直接改：
- `casting_round_01.json`
- `casting_gallery_30.json`
- `casting_selection.json`
- `production_dialogue.json`

## 環境變數

```bash
export MIMO_API_KEY="你的 MiMo API Key"
export MIMO_BASE_URL="https://api.xiaomimimo.com/v1"   # 預設可省略
# 可選：指定工作區根目錄（預設為此目錄）
export VOICEGEN_ROOT="/Users/yaowei/Documents/GameGod/VoiceGenerator - TTS"
```

## 常用命令

```bash
cd "/Users/yaowei/Documents/GameGod/VoiceGenerator - TTS/scripts"

# 1) 先 dry-run 確認
python3 generate_casting_samples.py --dry-run
python3 generate_voice_gallery.py --dry-run
python3 generate_production_dialogue.py --dry-run

# 2) 實際生成
python3 generate_casting_samples.py
python3 generate_voice_gallery.py
python3 generate_production_dialogue.py

# 4) 依官方目錄順序生成 208 個可比較樣本（已存在的會跳過）
python3 generate_tts_catalog.py

# 只先生成前 10 個，或指定一個類別；之後重跑會接續
python3 generate_tts_catalog.py --limit 10
python3 generate_tts_catalog.py --category base_emotion

# 5) 生成 Voice Seed Studio 首頁（左側生成紀錄）
python3 build_test_dashboard.py

# 5.1) 生成熱門模板的固定聲音與示範 WAV（需先啟動 run_dashboard.py）
python3 generate_hot_templates.py

# 6) 一鍵拉起 Voice Seed Studio（只要這一行；會啟動本機 API 與首頁）
python3 run_dashboard.py

# 7) 不開啟瀏覽器只更新輸出（CI/自動化可用）
python3 run_dashboard.py --no-open

# 8) 驗證電影／電視劇配音管線（不打 API）
python3 test_cinema_pipeline.py

# 9) ASR 驗收最新一段生成成品（會呼叫 MiMo-V2.5-ASR）
python3 verify_voice_take.py
```

> 提醒：總覽頁會讀取 `outputs/` 下每個子目錄的 `manifest.json`。
> 每次新增新測試（產生新的 outputs/xxx/manifest.json）後，先跑一次上面那行，
> 就會更新同一個 `outputs/index.html` 讓你可以直接切換看所有測試。

## 輸出資料夾整理

- 根目錄只保留 `scripts/` 與 `outputs/`。
- `outputs/` 的輸出規則：
- `outputs/index.html`：單一工作台首頁；左側只顯示每次生成的音檔紀錄，不再放測試頁籤
- `outputs/xxx/`：每一輪測試各自一個目錄，內含 `manifest.json`、`index.html`、`README.md`、音檔

`generate_tts_catalog.py` 會建立以下可切換測試目錄：

- `outputs/tts_catalog_voice_catalog/`：8 個官方具名音色 + `mimo_default` 預設別名
- `outputs/tts_catalog_base_emotion/`：9 個基礎情緒 × 9 個預置音色/預設別名
- `outputs/tts_catalog_compound_emotion/`：9 個複合情緒 × 中英基準音色
- `outputs/tts_catalog_overall_tone/`：9 個整體語調 × 中英基準音色
- `outputs/tts_catalog_timbre/`：9 個音色定位 × 中英基準音色
- `outputs/tts_catalog_persona_dialect/`：人設腔調、方言、角色扮演與唱歌
- `outputs/tts_catalog_audio_tags/`：停頓、呼吸、語速、笑哭與非語言標籤

Voice Seed Studio 會另外使用：

- `outputs/voice_seeds/<seed-id>/`：固定參考音檔與 `seed.json`（hash、來源、模型、建立時間）
- `outputs/voice_generations/`：指定種子後的 voice-clone 生成紀錄
- `outputs/hot_templates/`：熱門模板的固定聲音 WAV 與 `manifest.json`；每張模板都必須有可播放音檔
- `outputs/showcase/`：首頁古裝劇複合情緒示範

工作台流程：

1. 在首頁「文字設計」輸入聲音描述，或切換「上傳音檔」選擇 WAV/MP3；建立種子時先選「女性／男性（硬性）」或「中性／不指定」。
2. 建立後選擇種子，勾選複合情緒與強度；再選演繹方式、語速、音高、停頓、收句與導演補充，輸入台詞並生成。這些控制會寫入紀錄，方便同一角色重生同一種表演。
3. 性別鎖定會同時寫入建種提示與 `mimo-v2.5-tts-voiceclone` 生成提示；正式生成固定使用同一份參考音檔，聲音種子 hash 與性別會寫入生成紀錄，降低聲線偏離並方便追溯。
4. 首頁右上角「主題配色」可切換古裝月影、電影暗幕、清透日光或霓虹聲場；「熱門模板」分頁則是熱門台詞與完整生成配置，每張模板都有預先生成的 WAV，選擇你的聲音種子後可直接套用並生成。
5. 「電影／電視劇配音」分頁把每段戲拆成人物關係、目的、阻力、潛台詞與三段節拍；可用單一種子生成，也可勾選最多四個聲音種子依序批次試鏡。原始模板才會使用受信任的句級音訊標籤，台詞一經改寫就自動切換為乾淨文字。

熱門模板的聲音提示會要求真人一次錄製感：自然呼吸、細微不規則停頓、口語重音與情緒微變化，避免每字等長、客服播報腔與過度合成感。生成時會依問號、感嘆號、省略號、逗號和句號建立逐句語調走位，避免所有句尾套用同一個下墜曲線；「尾音放輕」也會被明確解讀成降低音量，而不是降低音高。

> 台詞欄只會送出原文；情緒、演繹與導演設定只作為控制提示，不會拼進朗讀文字。若模型把短台詞異常拉長，服務會自動重試，並依台詞長度套用停止與尾端靜音護欄。

> 性別鎖定是模型提示的硬性選角條件；上傳音檔時仍應選擇與參考音檔一致的性別。若參考音檔本身是男性，不能期待 voice-clone 穩定把它變成女性聲線。

官方清單與「可自訂」說明來源：

- https://mimo.mi.com/docs/usage-guide/speech-synthesis
- https://github.com/XiaomiMiMo/MiMo-Skills/blob/main/skills/mimo-v2-5-tts/SKILL.md

## 自訂路徑

所有腳本都支援 `--project-root`，預設會接到 `VOICEGEN_ROOT`（若未設會用程式所在工作區）。
你也可指定每個腳本的 profile / output：

```bash
python3 generate_casting_samples.py \
  --project-root "/path/to/your/workspace" \
  --profiles "/path/to/your/workspace/scripts/profiles/casting_round_01.json" \
  --output-dir "/path/to/your/workspace/outputs/casting_round_01"
```

所有輸出的音訊都會落在 `outputs/` 下，方便後續接 Unity / 其他流程。
