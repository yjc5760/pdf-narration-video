# pdf-narration-video 專案筆記

## 專案資訊
- **專案名稱**：pdf-narration-video
- **專案用途**：PDF 簡報自動生成簡報影片
- **資料夾位置**：`d:\pdf-narration-video`
- **GitHub Repo**：公開 (Public)
- **部署需求**：需要部署

## 目前狀態
- **2026-07-16**：使用 AntiGravity 進行專案初始化與收工。
  - `README.md` 已存在並保留。
  - 建立 `.gitignore` 排除暫存檔與金鑰 (`.env`, `work/`, `__pycache__/`)。
  - 建立 `ANTIGRAVITY.md` 記錄基本操作守則。
  - 成功初始化 Git Repo 並推送至 GitHub (Public)。
  - 排解了 MCP 伺服器啟動失敗的問題（找到實際路徑 `notebooklm-mcp.exe`）。

## 待辦事項 (Next Steps)
- [x] 設定 `git` 環境並執行 `git init`，並從遠端倉庫抓取最新專案。
- [x] 解決 `ffmpeg.exe` 檔案過大問題：從 `tools/` 移除並加入 `.gitignore`，改由系統層級 `winget` 安裝。
- [x] 將新的 PDF 放進 `input/` 資料夾，並建立新專案目錄 `結構動力學_SDOF到MDOF`。
- [x] 執行 `pdftoppm` 轉圖、編寫講稿並進行影片合成。
- [x] 處理後續影片生成的部署或執行需求。
- [x] 重構專案架構：引入 `init_project.bat` 自動化建檔與全域 `.env` 機制，免除手動複製腳本。

## 踩坑紀錄
- **大檔案上傳警告**：`tools/ffmpeg.exe` 與 `ffprobe.exe` 體積約 97MB，推送到 GitHub 時會觸發容量警告。已將其從版控移除，改透過腳本或 winget 在使用者的電腦進行全域安裝。
- **NotebookLM MCP 伺服器啟動失敗**：透過 `uv` 安裝的 MCP 套件提供了 `nlm.exe` (CLI 工具) 與 `notebooklm-mcp.exe` (MCP Server)。在設定檔中必須指定絕對路徑（例如 `C:\\Users\\yjc\\.local\\bin\\notebooklm-mcp.exe`）且不帶 `args`，否則會發生找不到執行檔或不支援子指令的錯誤。
- **Windows cmd 中文亂碼 (UnicodeEncodeError)**：當 Python 透過 cmd 執行並嘗試輸出中文字元時，會報錯 `UnicodeEncodeError: 'charmap'`。已在 `tools/run_azure.bat` 中加入 `chcp 65001 >nul` 與 `set PYTHONIOENCODING=utf-8` 徹底解決。
- **winget 安裝後環境變數未即時更新**：透過 `winget` 安裝 FFmpeg 後，當下正在執行的 Python / cmd / PowerShell 行程不會立刻吃到新的 `PATH`，導致 `pipeline.py` 在呼叫 `ffprobe` 時報錯 `FileNotFoundError: [WinError 2]`。需重開終端機或手動刷新環境變數。
