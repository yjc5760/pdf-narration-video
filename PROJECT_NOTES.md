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
- [x] 修復 DRY 架構的腳本相容性 bug (動態 `Path.cwd()` 與 `ffmpeg` 全域查找)。

## 踩坑紀錄
- **大檔案上傳警告**：`tools/ffmpeg.exe` 與 `ffprobe.exe` 體積約 97MB，推送到 GitHub 時會觸發容量警告。已將其從版控移除，改透過腳本或 winget 在使用者的電腦進行全域安裝。
- **NotebookLM MCP 伺服器啟動失敗**：透過 `uv` 安裝的 MCP 套件提供了 `nlm.exe` (CLI 工具) 與 `notebooklm-mcp.exe` (MCP Server)。在設定檔中必須指定絕對路徑且不帶 `args`，否則會發生找不到執行檔或不支援子指令的錯誤。
- **Windows cmd 中文亂碼與字節偏移 (UnicodeEncodeError / Parse Error)**：當 `.bat` 檔中包含 UTF-8 中文註解且未生效 `chcp 65001` 時，CMD 會因為 CP950 解碼錯誤導致切斷指令（拋出如 `THONIOENCODING is not recognized` 錯誤）。解法是 `.bat` 檔內改用純 ASCII (英文) 註解。
- **winget 安裝後環境變數未即時更新**：透過 `winget` 安裝 FFmpeg 後，當下執行的終端機不會立刻更新 `PATH`，導致 `pipeline.py` 報錯 `FileNotFoundError`。解法是在 `run_azure.bat` 內加入一段迴圈，自動搜尋 `%LOCALAPPDATA%\Microsoft\WinGet\Packages` 底下的 `ffmpeg\bin` 並動態加進 `PATH` 內。
- **共用腳本的路徑陷阱 (`__file__`)**：當把 `pipeline.py` 移入 `tools/` 並讓外層呼叫時，若程式內部使用 `Path(__file__).parent` 定位專案資源（如講稿或圖片），會發生讀取錯誤。解法是將專案基底路徑改為 `Path.cwd()`（獲取當前終端機工作目錄）。
