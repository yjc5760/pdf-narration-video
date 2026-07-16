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
- [x] 設定 `git` 環境並執行 `git init`
- [x] 透過 `gh repo create` 或手動建立 GitHub Repo 並推送。
- [ ] 將新的 PDF 放進 `input/` 資料夾，並依照 `ANTIGRAVITY.md` 規則建立新專案以生成影片。
- [ ] 處理後續影片生成的部署或執行需求。

## 踩坑紀錄
- **大檔案上傳警告**：`tools/ffmpeg.exe` 與 `ffprobe.exe` 體積約 97MB，推送到 GitHub 時會觸發容量警告 (上限 100MB)。若未來要替換版本，可考慮將其改為外部下載或加入 `.gitignore` 以免超出限制。
- **NotebookLM MCP 伺服器啟動失敗**：透過 `uv` 安裝的 MCP 套件提供了 `nlm.exe` (CLI 工具) 與 `notebooklm-mcp.exe` (MCP Server)。在設定檔中必須指定絕對路徑（例如 `C:\\Users\\yjc\\.local\\bin\\notebooklm-mcp.exe`）且不帶 `args`，否則會發生找不到執行檔或不支援子指令的錯誤。
