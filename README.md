# VoiceGenerator - TTS

![GitHub stars](https://img.shields.io/github/stars/zhudaandzhuer/VoiceGenerator---TTS?style=social)
![Python](https://img.shields.io/badge/python-3.10+-3776AB?logo=python&logoColor=white)
![MiMo](https://img.shields.io/badge/TTS-MiMo--V2.5-c86f61)

一套可直接上手的中文聲音資產作業系統，已封裝「聲音種子、表演種子、保真門禁、角色選角、場景連戲、製作匯出」完整流程。
專案目標是：  
- 以同一個聲音種子保留角色一致性  
- 讓複合情緒可反覆生產  
- 讓每次生成結果都能追溯（種子、情緒、參數、音檔）

## 專案特色

- 本地語音工作台（Dashboard）
  - 建立聲音種子（文字描述 / 上傳參考音檔）
  - 性別可強制指定（避免女聲變男聲、男聲變女聲）
  - 指定情緒、情緒強度、語速、音高、停頓、尾音、演繹方式後生成
  - 生成紀錄集中在首頁，方便追查
- 聲音資產系統
  - 每個聲音自動建立 Voice Passport，不再只是一個孤立 WAV
  - 同一角色可保存自然、近景、耳語、爆發、敘事等多個聲音錨點
  - 不可變版本血統與 Active 版本切換，改動可追溯、可回退
  - `.voicepack` 一鍵匯出參考音檔、護照、版本與認證報告
- 表演種子
  - 內建 12 組可重用表演配方，涵蓋近景生活流、忍住眼淚、古裝含蓄、懸疑低語、喜劇節拍等
  - 聲線身份與表演方法分離：換演法不重新設計角色音色
  - 可建立自訂表演種子，保存情緒弧線、語速、收句、錨點偏好與導演筆記
- 品質與製作
  - 每次生成自動寫入聲音版本、錨點與表演種子血統
  - WeSpeaker CN-Celeb ResNet34 以 256 維 speaker embedding 比對 Active 錨點；模型未安裝時自動退回本地訊號輪廓
  - 本地保真門禁同時檢查長度循環、聲紋相似度與聲學輪廓，異常 take 自動標記人工複核
  - 快速認證掃描參考健康、性別硬鎖、版本、多錨點、表演覆蓋與既有 take
  - 真實壓測可用四種相反演法驗證同一聲線；聲紋分數用於製作品管，不作法律身份鑑定
  - 角色選角助手依性別、年齡感、聲線語意、認證與錨點能力排序並解釋；可勾選最多四名用同一句台詞批次 A/B 試鏡
  - 場景連戲專案會保存 cast、逐句時間軸與 `production_manifest.json`
- 持久化製作佇列
  - 單句生成與 A/B 試鏡都能交給伺服器端佇列，關閉瀏覽器仍會繼續
  - 單工序列避免 API 暴衝與 manifest 競爭；每完成一個 take 就立即落盤
  - 支援逐項進度、取消、失敗隔離、只重試失敗項與整批重跑
  - 工作站重啟後會把執行中任務標為中斷，必須手動重試，避免無意重複計費
- 熱門模板
  - 內建多種熱門情境模板，保留每張模板的示範音
  - 可直接用自己的種子套用模板快速出片
- 電影／電視劇配音
  - 14 組原創場景，涵蓋愛情、家庭、商戰、懸疑、醫療、古裝、戰爭、校園、喜劇、科幻、警匪、諜戰與法庭
  - 每場都有既定情境、人物關係、當下目的、阻力、潛台詞與三段表演節拍
  - 支援單一聲線快速生成，或勾選最多四個聲音種子做批次試鏡
  - 原版台詞使用官方句級音訊標籤；改寫台詞會自動切換乾淨模式，避免念出錯置標籤
  - 6 組雙人對手戲：A／B 角色各自鎖定聲音種子，依接話反應逐句生成，再自動插入留白並合成完整場景
  - 每句同時保存獨立 WAV；不滿意時可只重生該句，完整場景會立即重新合成
- 古風聲音劇場（純音訊）
  - 聲音種子鎖定人物，古人說詞模板提供逐句情緒、語調與呼吸節拍
  - 內建 4 組本機演算法原創古風配樂，也能上傳自己的 WAV／MP3／M4A
  - 背景音樂會由實際人聲觸發 8:1 自動避讓；短房間反射、大殿、石亭、曠野等空間獨立選擇
  - 同時交付乾人聲、空間人聲、48 kHz WAV 母帶、256 kbps MP3 與完整 `scene.json`
  - 母帶目標約 −16 LUFS／−1.5 dBTP，避免配樂吃字與峰值爆音
- 媒體音訊工具
  - MP4／MOV／MKV／WebM／MP3／WAV／M4A 等格式轉 256 kbps MP3
  - Demucs 4 模型式人聲／BGM 分離，單聲道來源也能處理，不用左右聲道相消冒充去人聲
  - 去人聲 BGM 可一鍵帶回古風聲音劇場繼續配詞、配聲音
  - 轉檔與分離都是持久化任務，輸出原音 MP3、人聲 WAV／MP3、BGM WAV／MP3
- 自動化腳本
  - 批次產生不同角色庫、情緒庫、音色庫
  - 按 manifest 管理輸出，輸出目錄結構清楚
- 美學與可讀性修正
  - 語調控制改為逐句處理（問號、感嘆號、逗號、句號）
  - 尾音、停頓、情緒不會只剩「同一種下墜感」

## 一行啟動工作台

```bash
cd "/Users/yaowei/Documents/GameGod/VoiceGenerator - TTS"
python3 scripts/run_dashboard.py
```

以上會啟動本機 API + 開啟首頁（同一入口可管理全部流程）。
預設網址為 `http://127.0.0.1:8888/index.html`；如需臨時改用其他端口，可加上 `--port <端口>`。

## 環境需求與設定

- Python 3.10+
- 小米 MiMo API Key

```bash
cp scripts/.env.example scripts/.env
```

編輯 `scripts/.env`，填入：

```bash
export MIMO_API_KEY="你的 MiMo API Key"
export MIMO_BASE_URL="https://token-plan-sgp.xiaomimimo.com/v1"
export VOICEGEN_ROOT="/Users/yaowei/Documents/GameGod/VoiceGenerator - TTS"
```

> `scripts/.env` 已列入 `.gitignore`，不會被推到 GitHub。

## 快速開始

```bash
cd "/Users/yaowei/Documents/GameGod/VoiceGenerator - TTS"

# 確認依賴與環境
source scripts/.env

# 安裝本地聲紋驗證依賴並下載校驗過的固定版 WeSpeaker 模型
python3 scripts/setup_speaker_embedding.py

# 安裝 MP3／影片人聲分離模型（第一次分離會自動下載 htdemucs 權重）
python3 scripts/setup_audio_tools.py

# 只重建專案入口頁（可重複執行）
python3 scripts/build_test_dashboard.py

# 只想先起服務，不開啟瀏覽器
python3 scripts/run_dashboard.py --no-open

# 常用生成腳本
python3 scripts/generate_hot_templates.py
python3 scripts/build_test_dashboard.py
python3 scripts/generate_voice_gallery.py

# 離線驗證影視模板與防呆
python3 -m unittest discover -s scripts -p 'test_*.py' -v

# 用 MiMo ASR 驗收最新 take：檢查控制字、重複段落與台詞偏離
python3 scripts/verify_voice_take.py

# 驗收指定音檔（指定音檔時必須同時提供預期台詞）
python3 scripts/verify_voice_take.py --audio outputs/dialogue_scenes/<scene-id>/scene.wav --expected "完整台詞"
```

## 目錄結構（對外只保留 `scripts/` 與 `outputs/`）

- `scripts/`
  - 所有執行與服務程式
  - 含 MiMo API 封裝、模板清單、dashboard server、各類生成腳本
- `outputs/`
  - 所有生成結果、manifest、demo 與聲音種子紀錄
  - `outputs/index.html`：總覽首頁（歷史、模板、音檔）
  - `outputs/voice_seeds/*`：種子與設定紀錄
  - `outputs/voice_seeds/*/passport.json`：聲音護照、錨點與版本血統
  - `outputs/voice_generations/*`：正式生成結果
  - `outputs/dialogue_scenes/*`：雙人場景、逐句 WAV、完整 scene.wav 與可追溯 scene.json
  - `outputs/audio_scenes/*`：古人說詞乾聲、配樂 WAV／MP3 母帶與音景 manifest
  - `outputs/audio_scene_assets/bgm/*`：本機演算法原創古風配樂庫
  - `outputs/media_audio_jobs/*`：MP4→MP3、人聲與 BGM 分離結果
  - `outputs/performance_seeds/*`：自訂表演種子
  - `outputs/continuity_projects/*`：連戲專案與製作 manifest
  - `outputs/quality_reports/*`：保真認證報告
  - `outputs/production_jobs/*`：持久化製作佇列、逐項進度與錯誤
  - `outputs/models/*`：本機聲紋模型；大型 ONNX 不進 Git，使用 setup 腳本下載並校驗
  - `outputs/voicepacks/*`：可交付的 `.voicepack` 聲音資產包
  - `outputs/hot_templates/*`：熱門模板示範

## 支援腳本一覽

- `scripts/run_dashboard.py`：一鍵啟動工作台
- `scripts/voice_studio_server.py`：本機 API 與生成功能
- `scripts/ancient_audio_templates.py`：古人說詞逐句表演譜、配樂與空間預設
- `scripts/audio_scene_mixer.py`：配樂避讓、空間效果、WAV／MP3 母帶與音訊 QC
- `scripts/audio_scene_queue.py`：古風聲音音景持久化任務
- `scripts/media_audio_tools.py`：MP4→MP3 與 Demucs 模型式人聲分離
- `scripts/media_tool_queue.py`：媒體音訊持久化任務
- `scripts/setup_audio_tools.py`：安裝固定版 Demucs 4.0.1
- `scripts/production_queue.py`：可恢復、可取消、可重試的持久化製作佇列
- `scripts/seed_asset_system.py`：護照、多錨點、版本、表演種子、認證、選角與 voicepack
- `scripts/speaker_embedding.py`：WeSpeaker ONNX speaker embedding 與保真門禁
- `scripts/setup_speaker_embedding.py`：安裝依賴並下載固定 revision／SHA256 的聲紋模型
- `scripts/studio_client.py`：模組化 Voice Seed OS 客戶端
- `scripts/build_test_dashboard.py`：重建總覽頁
- `scripts/generate_hot_templates.py`：重建熱門模板音檔
- `scripts/generate_casting_samples.py`：角色試音
- `scripts/generate_voice_gallery.py`：聲線庫批次生成
- `scripts/generate_tts_catalog.py`：官方音色/情緒/腔調清單生成器
- `scripts/generate_showcase.py`：劇情示範音檔
- `scripts/generate_production_dialogue.py`：劇本批次生成
- `scripts/cinema_templates.py`：原創影視場景、人物目的、潛台詞與表演節拍
- `scripts/dialogue_scene_templates.py`：六組原創雙人對手戲、A／B 角色目的、接話反應與逐句留白
- `scripts/test_cinema_pipeline.py`：影視配音離線回歸測試
- `scripts/test_dialogue_scene_pipeline.py`：雙人選角、逐句生成、WAV 合成與防呆回歸測試
- `scripts/test_seed_asset_system.py`：新資產模型、保真門禁、選角、連戲與 voicepack 離線回歸
- `scripts/test_production_queue.py`：持久化、失敗隔離、取消與重啟恢復測試
- `scripts/test_speaker_embedding.py`：聲紋模型可用性、降級與門檻測試
- `scripts/verify_voice_take.py`：用 MiMo ASR 驗收生成台詞與控制字洩漏

## 雙人對手戲工作流

1. 開啟「電影／電視劇配音」分頁，在「雙人對手戲組裝台」選一場戲。
2. 分別替 A、B 角色指定不同聲音種子，並選擇對手反應留白。
3. 點擊「生成完整雙人場景」；完成後可播放或下載完整 WAV，也能逐句試聽。
4. 某一句表演不對時，點擊「只重生這一句」。系統只重做該 take，其他句不動，並重建完整場景。

專案附帶一場實際 API＋ASR 驗收成品：`outputs/dialogue_scenes/scene_20260809_020345_rain-platform-choice_18ef825652/`。完整場景 ASR 相似度 97.01%，未偵測到控制詞洩漏或重複段落。

## 給按下 Star 的你

如果你覺得這套工具有幫到你，幫我按星星會更有動力持續補更多模板、更多真人感聲線與更完整的劇本串接流程 🙌  
[前往 GitHub 按 Star](https://github.com/zhudaandzhuer/VoiceGenerator---TTS)

按了 star 以後也可以直接留 issue / PR 你看到的 bug 或需求，我們會持續把它變得更實用。

## 相關連結

- [小米 MiMo 官方文件](https://github.com/XiaomiMiMo/MiMo-Skills/blob/main/skills/mimo-v2-5-tts/SKILL.md)
- [小米 MiMo API 使用指南](https://mimo.mi.com/docs/usage-guide/speech-synthesis)
