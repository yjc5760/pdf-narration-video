# 簡報轉影片 Pipeline 使用說明

## 資料夾結構(2026-07-15 整理)

```
pdf-narration-video/
├─ .agents/      ← AntiGravity 原生技能區 (含 pdf-narration-video)
├─ input/        ← 來源 PDF 集中放這裡(新簡報放進來)
├─ output/       ← 成品影片+字幕,依專案命名(SS-2023-1.mp4 / .srt)
├─ tools/        ← 共用工具:pipeline.py 等腳本、heteronyms.json
├─ SS-2022-1/    ← 專案工作區(narration.md、images/、work/ TTS快取)
└─ SS-2023-1/    ← 同上
```

慣例:開新專案時請直接在根目錄執行 `init_project.bat 您的檔案.pdf`，腳本會幫您建好資料夾、轉好圖片並產生講稿模板。之後進入專案執行 `..\tools\run_azure.bat` 即可（它會自動讀取根目錄的 `.env`）。跑完把
`output/final_video.mp4` 改名成專案名複製到根目錄 `output/`。
work/ 內的 page-*.json + page-*.mp3 是付費 TTS 快取,改講稿重跑前不要刪。

## 目前狀態:已跑通正式版(Azure TTS + 精準字幕)

用 `SS-2023-1-NBLM.pdf`(15頁)跑過完整流程,包含抓出並修正一個關鍵 bug,
最終確認字幕跟配音對得上。這套流程已經打包成可重複套用的 Claude skill
(`pdf-narration-video`),之後有新簡報要轉影片,直接請 Claude 用這個 skill
處理,不用重新從頭解釋一次。

```
PDF每頁 → 圖片(pdftoppm)
逐頁講稿(narration.md)→ Azure TTS 合成語音 + 逐詞時間戳
音頻時長 + 時間戳 → 該頁影片片段(圖片+音頻,FFmpeg)
所有片段串接 → 最終影片
講稿文字 + 精準時間戳 → SRT 字幕(逐字對齊,不是估算切分)
```

輸出:`output/final_video.mp4` + `output/final_video.srt`

歷史示範版本(`SS-2023-1-demo.mp4` / `.srt`)是最早用 espeak-ng(離線、免費、
機械音)驗證流程能跑通留下的產物,字幕時間軸是「按文字比例切分」的估算值,
不是真正逐字對齊,僅供參考不建議繼續使用。

## 已修正的關鍵 bug:Azure 逐詞時間戳 ≠ 逐字時間戳

Azure TTS 的 `word_boundary` 事件是「逐詞」時間戳(一個事件常常對應 2 個以上
中文字),不是逐字。原本的程式碼把 chunk 的字數直接當索引去切
`word_timestamps` 陣列(誤把每個 entry 當成 1 個字),導致字幕越往後偏移越
嚴重(實測偏移可達好幾秒)。

`pipeline.py` 裡新增的 `_expand_word_times()` / `_align_char_times()` 已經
修正這個問題:先把逐詞時間戳內插展開成逐字時間戳,再對齊回原文(標點符號
沿用前一個字的結束時間),確保字幕邊界精準對應語音。**如果之後要改動 SRT
產生邏輯,請保留這個對齊步驟,不要繞過它自己重寫索引。**

## 換成正式配音

正式使用時,把 TTS 引擎換成 Azure 或 ElevenLabs,這樣除了語音自然很多,還
能拿到真正的逐字時間戳,字幕會精準對齊每個字,不再是估算切分。

### 用 Azure TTS(推薦,中文/台灣腔道地,本專案已驗證)

```bash
pip install azure-cognitiveservices-speech
```

在專案資料夾建立 `.env`(不要把金鑰寫進對話或存進 git):

```
AZURE_SPEECH_KEY="你的金鑰"
AZURE_SPEECH_REGION="你的區域,例如 southeastasia、eastasia"
```

**Windows 使用者(命令提示字元 cmd,不是 bash/PowerShell)**直接執行:

```
run_azure.bat
```

這個批次檔會自動讀 `.env` 設定環境變數再執行 `python pipeline.py --engine azure`。

macOS/Linux 使用者:

```bash
set -a; source .env; set +a
python3 pipeline.py --engine azure
```

`pipeline.py` 裡的 `synth_azure()` 預設用 `zh-TW-HsiaoChenNeural`,可以在
程式裡改成你想要的聲音(例如 `zh-TW-YunJheNeural`)。

### Windows 常見卡關

- `ffprobe`/`ffmpeg` 沒裝的話,錯誤會在 TTS 呼叫「成功之後」才跳出來
  (`FileNotFoundError: [WinError 2]`),容易誤判成配音失敗——其實是缺工具,
  不是金鑰或程式碼問題。用 `winget install ffmpeg` 安裝,**裝完要開新的命令
  提示字元視窗**讓 PATH 生效。
- 字幕顯示方塊亂碼:`final_video.mp4` 沒有燒錄字幕,是外部 `.srt` 檔,某些
  播放器對 UTF-8 中文字幕支援不好才會這樣。換 VLC,或用下面指令燒錄進畫面:
  ```
  ffmpeg -y -i output/final_video.mp4 -vf "subtitles=output/final_video.srt:force_style='FontName=Microsoft JhengHei,FontSize=28,PrimaryColour=&Hffffff,OutlineColour=&H000000,BorderStyle=1,Outline=2'" -c:a copy output/final_video_captioned.mp4
  ```

### 用 ElevenLabs

```bash
pip install requests
export ELEVENLABS_API_KEY="你的金鑰"

python3 pipeline.py --engine elevenlabs
```

`synth_elevenlabs()` 裡的 `voice_id` 要換成你 ElevenLabs 帳號裡的聲音 ID。

## 檔案說明

| 檔案 | 用途 |
|---|---|
| `pipeline.py` | 核心邏輯:講稿解析、三種 TTS 引擎、SRT 產生(含已修正的逐字對齊)、FFmpeg 合成、每頁快取 |
| `process_pages.py` | 分批處理頁面用,`python3 process_pages.py 起始頁 結束頁 --engine azure`(也可直接用 `pipeline.py --pages 1-5`) |
| `assemble.py` | 所有頁面處理完後,串接成最終影片+字幕(讀 `work/page-NN.json` 快取) |
| `run_azure.bat` | Windows(cmd)專用:自動讀 `.env` 設環境變數再跑 `pipeline.py --engine azure` |
| `.env` | 存放 `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION`(不要進版控) |
| `narration.md` | 逐頁講稿,`pipeline.py` 實際讀取的檔案(格式:`## 頁 N — 標題`) |
| `SS-2023-1-narration-script.md` | 同一份講稿的可讀版備份 |

## 如果你要換一份新簡報

這個流程已經打包成 Claude skill(`pdf-narration-video`),之後只要跟 Claude 說
「把這份PDF轉成講解影片」之類的話就會自動套用,不用照著下面手動操作。手動流程:

1. 將您的 PDF 放到 `input/` 資料夾中（或其他您喜歡的路徑）。
2. 在根目錄執行自動化腳本：
   ```bash
   init_project.bat input/你的檔案.pdf
   ```
   它會自動建立專案資料夾、呼叫 `pdftoppm` 轉出圖片，並產生對應頁數的 `narration.md` 講稿模板。
3. 進入新建的專案資料夾，讀懂每一頁圖片內容，並在 `narration.md` 的對應區塊填寫口語化的講稿。
4. 確保根目錄已經有一份 `.env` 設定檔（包含 `AZURE_SPEECH_KEY` 與 `AZURE_SPEECH_REGION`）。
5. 在專案資料夾內執行：
   ```bash
   ..\tools\run_azure.bat
   ```
   (macOS/Linux 則執行 `set -a; source ../.env; set +a; python3 ../tools/pipeline.py --engine azure`)

## 2026-07 優化紀錄

- **標點集合修正**:原本只含半形 `,!?`,但講稿實際用的是全形逗號/問號,導致
  斷句失效、對齊時可能誤吃時間戳。已改為全形+半形都涵蓋
- **長句二次拆分**:超過 22 字的句子會等分拆成多條字幕(原 `max_chars` 參數
  之前沒有實際作用)
- **每頁 TTS 快取**:結果存 `work/page-NN.json`,講稿沒改就不重打 Azure(省錢
  省時);改某頁講稿只重跑那頁。`--force` 可強制全部重跑
- **`--pages 3-7`**:pipeline.py 可只處理指定頁,其餘頁用快取串接
- **前置檢查**:開跑前先確認每頁講稿都有對應圖片,缺圖直接中止,不浪費 TTS 額度
- **頁間停頓**:每頁尾補 0.6 秒靜音(`PAGE_TAIL_SILENCE`),不再首尾硬接;
  SRT 時間軸也改用片段實際長度推進,避免累積偏移
- **SSML escape**:講稿含 `&` `<` `>` 不會再讓 Azure 掛掉
- **錯誤訊息**:ffmpeg/TTS 失敗時會印出 stderr,不再吞掉
- **process_pages.py 支援 `--engine`**:之前寫死 espeak,分批模式沒辦法跑 Azure
- **Azure 音檔改存 `.mp3`**(實際格式本來就是 MP3);靜態圖改 10fps 編碼,更快更小
- **run_azure.bat**:容忍 `.env` 的空行/`#` 註解,失敗會停住顯示錯誤；已加入 `chcp 65001` 與 `PYTHONIOENCODING=utf-8` 以解決 Windows CMD 下的 `UnicodeEncodeError` 亂碼錯誤
- **注意**:舊的 `work/` 產物(25fps 片段、`manifest.json`)與新版不相容,
  升級後第一次跑前請先清空 `work/`

## 已知限制 / 之後可以優化的地方

- 影片統一輸出 1920x1080,若簡報比例不是 16:9,圖片會加黑邊(letterbox)
- 目前是「整段話配一張靜態圖」,如果想要更豐富的視覺效果(局部放大、紅圈
  聚焦動畫、逐字浮現字幕、頁面轉場),可以用 HyperFrames MCP 針對重點頁面
  另外做動態場景(已在對話中示範過第 6 頁的效果),取代靜態圖+FFmpeg硬切的
  部分
