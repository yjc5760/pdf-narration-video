# pdf-narration-video — PDF 簡報轉語音講解影片

## 這個專案在做什麼
把 NotebookLM 產生的簡報 PDF 轉成有精準逐字字幕的中文語音講解影片。
完整工作流程定義在原生技能檔案 `.agents/skills/pdf-narration-video/SKILL.md` 中。
做影片任務時先讀它，不要自己重新發明流程。

## 資料夾結構(必須遵守)
```
input/       來源 PDF 集中放這裡
output/      成品影片+字幕,依專案命名(例:SS-2023-1.mp4 / .srt)
tools/       共用工具:pipeline.py 等腳本、heteronyms.json (要改腳本改這裡)
SS-XXXX-X/   每個專案一個資料夾:narration.md、images/、work/
```

開新專案:
1. 準備好 PDF 並執行 `init_project.bat 您的檔案.pdf` 建立專案。
2. 進入專案資料夾修改 `narration.md` 講稿。
3. 在專案內執行 `..\tools\run_azure.bat` 產生影片（自動往上讀取根目錄的 `.env`）。
4. 跑完把 output/final_video.mp4 改成專案名,複製到根目錄 output/。

## 鐵則
1. **絕不刪 `work/` 裡的 `page-*.json` + `page-*.mp3`** ——那是付費 Azure TTS
   的快取,刪了改一頁講稿就要整份重新配音。clip-*.mp4 可刪(可重建)。
2. **檔案搬移一律 cp → 驗證目的地 → 才 rm 來源,禁止 mv**(這個掛載環境的
   mv 曾造成檔案遺失,靠資源回收筒救回)。
3. **`.env` 內含 Azure 金鑰**:不要讀出內容、不要回顯、不要存進記憶或提交。
4. FFmpeg / Poppler 已改為全域安裝（可透過 `tools/install_deps.bat` 或 winget 安裝），不再內附 exe 檔以節省版控空間。
5. 執行環境是 Windows cmd(不是 bash/PowerShell),給使用者的指令用 cmd 語法
   或包成 .bat。

## 現況備註(2026-07-19)
- tools/pipeline.py 是 v2:支援 `[[顯示|朗讀]]` 語法、`--verify` ASR 發音回驗
  (用同一組 Azure 金鑰)、faststart、產出後品質三檢。
- `tools/run_azure.bat` 已加入 UTF-8 編碼強制設定 (`chcp 65001` / `PYTHONIOENCODING=utf-8`)，避免 Windows 終端機遇到中文字元時產生 `UnicodeEncodeError`。
- 各專案資料夾內不再存放腳本正本。執行時一律呼叫 `..\tools\run_azure.bat` 共用最新版流程。
