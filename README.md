# VoiceGenerator - TTS

![GitHub stars](https://img.shields.io/github/stars/zhudaandzhuer/VoiceGenerator---TTS?style=social)
![Python](https://img.shields.io/badge/python-3.10+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

一套可直接上手的中文語音實驗與生成工作區，已封裝「聲音種子建立、情緒生成、模板復用、首頁展示」完整流程。  
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
- 熱門模板
  - 內建多種熱門情境模板，保留每張模板的示範音
  - 可直接用自己的種子套用模板快速出片
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

# 建立專案入口頁（可重複執行）
python3 scripts/run_dashboard.py --no-open

# 只想先起服務，不開啟瀏覽器
python3 scripts/run_dashboard.py --no-open

# 常用生成腳本
python3 scripts/generate_hot_templates.py
python3 scripts/build_test_dashboard.py
python3 scripts/generate_voice_gallery.py
```

## 目錄結構（對外只保留 `scripts/` 與 `outputs/`）

- `scripts/`
  - 所有執行與服務程式
  - 含 MiMo API 封裝、模板清單、dashboard server、各類生成腳本
- `outputs/`
  - 所有生成結果、manifest、demo 與聲音種子紀錄
  - `outputs/index.html`：總覽首頁（歷史、模板、音檔）
  - `outputs/voice_seeds/*`：種子與設定紀錄
  - `outputs/voice_generations/*`：正式生成結果
  - `outputs/hot_templates/*`：熱門模板示範

## 支援腳本一覽

- `scripts/run_dashboard.py`：一鍵啟動工作台
- `scripts/voice_studio_server.py`：本機 API 與生成功能
- `scripts/build_test_dashboard.py`：重建總覽頁
- `scripts/generate_hot_templates.py`：重建熱門模板音檔
- `scripts/generate_casting_samples.py`：角色試音
- `scripts/generate_voice_gallery.py`：聲線庫批次生成
- `scripts/generate_tts_catalog.py`：官方音色/情緒/腔調清單生成器
- `scripts/generate_showcase.py`：劇情示範音檔
- `scripts/generate_production_dialogue.py`：劇本批次生成

## 給按下 Star 的你

如果你覺得這套工具有幫到你，幫我按星星會更有動力持續補更多模板、更多真人感聲線與更完整的劇本串接流程 🙌  
[前往 GitHub 按 Star](https://github.com/zhudaandzhuer/VoiceGenerator---TTS)

按了 star 以後也可以直接留 issue / PR 你看到的 bug 或需求，我們會持續把它變得更實用。

## 相關連結

- [小米 MiMo 官方文件](https://github.com/XiaomiMiMo/MiMo-Skills/blob/main/skills/mimo-v2-5-tts/SKILL.md)
- [小米 MiMo API 使用指南](https://mimo.mi.com/docs/usage-guide/speech-synthesis)

