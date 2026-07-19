# pdf-narration-video 專案指引 (ANTIGRAVITY.md)

## 專案核心目標
- **專案名稱**：pdf-narration-video
- **專案用途**：讀取 PDF 簡報並自動生成帶有精準字幕與 TTS 配音的簡報影片。

## 關鍵開發規則
1. **工作目錄約定**：
   - `input/`：存放所有的原始 PDF 檔案。
   - `output/`：存放最終產出的成品影片與字幕（`.mp4`, `.srt`）。
   - `tools/`：存放共用的 Python 腳本等核心工具。
   - 個別專案目錄（例如 `SS-2023-1/`）：由 `init_project.bat` 自動建立，存放講稿 (`narration.md`)、圖片 (`images/`) 與快取 (`work/`)。
2. **檔案操作鐵則**：
   - 絕對禁止刪除 `work/` 裡面的 TTS 快取檔（`page-*.json`, `page-*.mp3`），否則會導致浪費 TTS API 額度。
   - 移動檔案一律使用 `cp` 驗證後再刪除來源，禁止直接使用 `mv`。
   - `.env` 檔案內包含 Azure 金鑰，禁止顯示於對話中或 commit 至版控系統。
3. **執行環境限制**：
   - 主要執行環境為 Windows cmd（非 PowerShell 或 Bash）。提供指令時，請優先使用 cmd 相容語法，或將其包裝於 `.bat` 檔中執行。

## 工作流指令支援
- 本專案支援 `05-workflow` 懶人包指令：「開工」、「收工」、「初始化專案」。請遵循標準化流程更新狀態與筆記。
