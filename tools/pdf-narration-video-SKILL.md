---
name: pdf-narration-video
description: 把 PDF 簡報(投影片、教材、懸賞單式解析等)自動轉換成有精準逐字字幕的中文語音講解影片——讀懂每一頁內容寫逐頁講稿、用 Azure TTS(或 ElevenLabs)配音取得逐字時間戳、產生真正對齊語音的 SRT 字幕、FFmpeg 合成最終 MP4。當使用者說「把這份PDF轉成影片」「幫我做這份簡報的語音講解影片」「這份PDF可以配音做成教學影片嗎」「生成有字幕的解說影片」,或提到要把投影片/PDF變成有旁白配音的影片、需要中文TTS+精準字幕同步,就要主動使用這個 skill,即使使用者沒有講出「hyperframes」「pipeline」等字眼也要觸發。目標執行環境預設 Windows(cmd,不是 bash/PowerShell)。
---

# PDF 簡報轉語音講解影片

把一份 PDF(通常是 NotebookLM 或簡報軟體產生的逐頁圖文投影片)轉換成一支有精準字幕、
中文語音講解的 MP4 影片。這套流程已經在實戰專案裡跑通、抓出並修正過一個關鍵 bug
(見下方「已知陷阱」),請直接沿用 `scripts/pipeline.py`,不要重新從零實作 TTS/SRT 對齊邏輯
——那個邏輯比看起來難,重寫很容易重踩同一個坑。

## 整體流程

```
PDF 每頁 → 圖片(pdftoppm)
逐頁讀懂內容 → 寫逐頁講稿(narration.md)
講稿 → TTS 合成語音 + 逐字/逐詞時間戳(Azure 或 ElevenLabs)
語音時長 + 時間戳 → 該頁影片片段(圖片+音頻,FFmpeg)
所有片段串接 → 最終影片
講稿文字 + 精準時間戳 → SRT 字幕(不用額外做語音辨識)
```

## 執行步驟

### 1. 確認專案資料夾與素材

在使用者的專案資料夾裡(例如 `工作資料夾/專案名稱/`)準備好:
- 來源 PDF(使用者提供)
- 把 `scripts/pipeline.py`、`scripts/process_pages.py`、`scripts/assemble.py`、
  `scripts/run_azure.bat`、`references/heteronyms.json` 複製進這個資料夾

### 2. PDF 轉圖片

```
pdftoppm -jpeg -r 150 你的檔案.pdf images/slide
```

會產生 `images/slide-01.jpg` ... `images/slide-NN.jpg`。如果環境沒有 `pdftoppm`,
它是 poppler-utils 的一部分,先確認有沒有裝。

### 3. 讀懂內容,寫逐頁講稿

用 Read 工具逐頁打開 `images/slide-NN.jpg`(不要跳過任何一頁,PDF 常常沒有文字層,
純粹是圖片,必須用視覺理解),為每一頁寫講稿。

**角色設定**:你是大學土木工程系的資深教授,專門為學生講解台灣結構技師國家考試
的解題內容。教學風格「淺顯易懂、邏輯清晰、親切且具啟發性」,擅長將生硬的規範與
複雜的力學推導,轉化為工程師的直覺觀念。(若簡報主題明顯不是工程考題,改用該領域
同等資深教師的口吻,其餘規則不變。)

**核心寫作規則(絕對遵守)**:

1. **避開數學公式朗讀**:遇到數學公式、代數推導、或代入公式的計算過程,**絕對
   不要逐字唸出來**(例如不要唸「P 等於 A 乘以 F y」)。必須轉換為引導式語句,
   例如:「請同學看一下簡報上的公式推導過程」「我們把數值代入簡報上的算式」
   「請參考圖表」,讓學生自己看簡報。
2. **語速與字數控制**:以一般授課語速(約每分鐘 180~200 字)為基準,依此估算
   每頁講稿字數(例如想讓該頁停留約 40~60 秒,就寫 120~200 字)。
3. **語氣口語化**:這是一份「講稿」,使用口語化詞彙(如:接著、然後、大家請看、
   要注意的是),避免生硬的書面用語,不要逐字照搬投影片上的條列文字。
4. **標點密度=停頓密度**:中文 TTS 每個標點都是一個停頓,逗號太密會變成
   機關槍式旁白。以「呼吸群」為單位下逗號(每個語調單位約 8~22 字),
   句首連接詞後面不要馬上加逗號(「接著我們看」而非「接著,我們看」),
   零碎短句合併;刻意的列舉節奏(「先看規範、再看圖、最後代入」)可以保留。
5. **破音字與難唸字**:掃一遍講稿裡的 還/重/長/得/差/載/應/強 等多音字
   (完整地雷表見專案裡的 `heteronyms.json`,pipeline 執行時也會自動掃描提醒)。
   Azure 通常判斷正確,但高風險詞建議改寫(還是→仍然、重新→再次),
   或搭配 `--verify` 回驗確認。
6. **顯示文/朗讀文分離語法**:字幕要顯示的字和 TTS 要唸的字不同時,
   用 `[[顯示|朗讀]]` 標記,例如:
   - 版本號:`[[4.5|四點五]]` → 字幕顯示 4.5,TTS 唸「四點五」
   - 英文縮寫:`[[SRSS|S R S S]]` → 唸出逐字母
   - TTS 老是唸錯的字:餵同音替身字,字幕仍顯示正確字(如 `[[換|喚]]`)
   字幕時間戳會自動對齊,不用手動處理。

寫成 `narration.md`,格式**必須**完全符合 `pipeline.py` 的 `parse_narration()` 解析規則:

```markdown
## 頁 1 — 這頁的標題
這一頁的講稿內容,可以是好幾句話。
---

## 頁 2 — 下一頁標題
第二頁講稿內容。
---
```

- `## 頁 N — 標題` 這一行的格式固定,頁碼要對應 `images/slide-NN.jpg` 的編號
- 每頁結尾用單獨一行 `---` 分隔
- 講稿寫完後,**先給使用者看過確認**再進到配音步驟(除非使用者明確說直接做到底)——
  配音跟剪輯比較花時間,講稿階段改字比事後重跑省很多力氣

參考範例見 `references/narration_template.md`。

### 4. 設定 TTS 金鑰

Azure(預設,中文/台灣腔道地,有 word boundary 時間戳):

```
pip install azure-cognitiveservices-speech
```

在專案資料夾建立 `.env`:

```
AZURE_SPEECH_KEY="使用者的金鑰"
AZURE_SPEECH_REGION="使用者的區域,例如 southeastasia、eastasia"
```

**不要把金鑰直接貼在對話或存進記憶裡**——請使用者自己在 `.env` 檔案裡貼上,或使用者貼給你
時就只用在當次執行,不要回顯或持久化到 memory。

如果使用者是在你自己(agent)的沙箱環境裡執行(而非使用者本機終端機),記得先測一下
沙箱能不能連到 Azure 的網域(`*.api.cognitive.microsoft.com`)——很多沙箱有網路白名單,
連不出去的話,金鑰本身可能完全沒問題,只是網路連不到,不要誤判成金鑰錯誤,改請使用者
在自己電腦的終端機執行。

### 5. 執行 pipeline

Windows 使用者通常用的是命令提示字元(cmd),不是 bash/PowerShell,所以：

```
run_azure.bat
```

這個批次檔會自動讀 `.env` 設定環境變數再執行 `python pipeline.py --engine azure`,
使用者不用自己打 `export` / `set` 指令(那些在 cmd 裡常常打錯或格式不對)。

如果簡報頁數很多、擔心單次執行逾時,改用分批模式:
`python pipeline.py --engine azure --pages 1-5` 逐批跑(每頁 TTS 結果會快取在
`work/page-NN.json`,講稿沒改就不會重打付費 TTS;`--force` 強制重跑),或用
`scripts/process_pages.py 起始頁 結束頁 --engine azure` + `scripts/assemble.py`
(**注意要帶 `--engine azure`,不帶預設是 espeak 機械音**)。

執行完會產生:
- `output/final_video.mp4`(含 faststart,可直接上傳網路串流播放)
- `output/final_video.srt`(逐字精準對齊)
- `output/verify_frame.png`(第 3 秒抽出的畫面,供目視比對)

### 5.5 產出後品質檢查(pipeline 會自動執行,但結果要看)

pipeline 結束前會自動跑三項檢查,**不要忽略它的輸出**:
1. **音訊 bitrate**:抓「技術上有聲音但近乎無聲」的失敗(正常約 192kbps,
   出現 2kbps 或找不到音訊串流=TTS 或合成失敗)
2. **總長度**:實際影片長度與各頁片段合計比對
3. **抽 frame**:用 Read 工具打開 `output/verify_frame.png` 目視確認——
   畫面必須是**這一批**投影片的第一頁,不是舊專案的殘留檔

### 5.6(可選但建議)ASR 發音回驗

```
python pipeline.py --engine azure --verify
```

用 Azure STT(**同一組金鑰,不需額外申請**)把每頁合成音檔辨識回文字、
與講稿比對相似度,抓出 TTS 唸錯的破音字/英文/數字。結果寫入
`output/verify_report.md`,回驗結果會快取(講稿沒改不重跑)。

**判讀準則(重要,避免無限重試)**:
- 同音異字(報到↔報導、儀式↔意識)= ASR 誤報,音檔其實是對的 → 放行
- 有裝 `pypinyin` 時會自動加算無聲調拼音相似度,排除大部分同音字誤報
- 只有「關鍵詞/數字沒辨識出來」或「多次合成同一處同一種錯」才是 TTS 真的唸錯
  → 改寫該詞,或用 `[[顯示|朗讀]]` 餵同音替身字
- 不要為了讓分數過門檻反覆重跑——字幕用的是講稿原文,投影片上也有正確文字,
  觀眾有三重冗餘,確認關鍵詞有唸對就可以出貨

### 6.(可選)字幕燒錄

`final_video.mp4` 本身沒有燒錄字幕,只有外部 `.srt`。如果使用者的播放器顯示字幕是
方塊亂碼(常見於某些播放器對外部 UTF-8 中文字幕支援不好),提供兩個方案:

1. 換 VLC 播放(通常直接正常)
2. 燒錄進畫面,保證任何播放器/平台都正常顯示:

```
ffmpeg -y -i output/final_video.mp4 -vf "subtitles=output/final_video.srt:force_style='FontName=Microsoft JhengHei,FontSize=28,PrimaryColour=&Hffffff,OutlineColour=&H000000,BorderStyle=1,Outline=2'" -c:a copy -movflags +faststart output/final_video_captioned.mp4
```

`FontName` 用目標系統上實際有的中文字型(Windows 內建可用 `Microsoft JhengHei`)。

## Windows 環境常見卡關

詳細除錯步驟見 `references/windows-troubleshooting.md`,摘要:

- 使用者可能會照抄 bash/PowerShell 語法貼進 cmd 導致報錯——cmd 沒有 `#` 註解、沒有
  `export`/`set -a`,一律給 cmd 語法或用 `.bat` 包起來
- `ffprobe`/`ffmpeg` 沒裝會在 TTS 成功之後才報 `FileNotFoundError`(容易誤判成配音
  失敗,其實配音是成功的,只是後面合成影片那一步缺工具)——用 `winget install ffmpeg`
  裝,裝完**必須開新的命令提示字元視窗**讓 PATH 生效
- 如果 winget 裝完新視窗還是找不到指令,把 `ffmpeg.exe`/`ffprobe.exe` 直接複製進
  專案資料夾也可以(Windows 執行程式會先找目前資料夾)

## 已知陷阱(務必留意,不要重踩)

**Azure 逐詞時間戳 ≠ 逐字時間戳。** Azure TTS 的 `word_boundary` 事件是「逐詞」
(一個事件常常對應 2 個以上中文字),不是逐字。如果直接把「chunk 的字數」當索引去切
`word_timestamps` 陣列(把每個 entry 當成 1 個字),字幕會隨著頁面越後面偏移越嚴重,
使用者會回報「字幕跟配音搭不起來」。`scripts/pipeline.py` 裡的 `_expand_word_times()` /
`_align_char_times()` 已經修正這個問題(先把逐詞時間戳內插展開成逐字,再對齊回原文,
標點符號沿用前一個字的結束時間)。**直接用這份 pipeline.py,不要重新手刻對齊邏輯。**
ElevenLabs 因為原生就是逐字時間戳,不受此問題影響。

## 選配:HyperFrames MCP 加值

如果使用者想要比「靜態圖+配音」更豐富的視覺效果(局部放大、紅圈聚焦動畫、卡拉OK
逐字字幕、頁面轉場),而且環境裡有 HyperFrames MCP(HeyGen)可用,可以用
`compose` 工具針對重點頁面另外做一個動態場景當範例,confirm 使用者滿意後再決定要不要
把整份簡報都換成 HyperFrames 版本。這是加值選項,不是必要步驟——`pipeline.py` 產出的
FFmpeg 版本已經是完整可用的成品。

**🔴 混剪警告(靜態頁片段 + HyperFrames 動態場景串接時務必遵守)**:
不同來源的片段**不能**用 concat demuxer + `-c copy` 串接——VLC 播得動,但
Windows 內建播放器等嚴格播放器會直接拒播(且 `ffmpeg -v error` 掃描還是乾淨的,
「掃描沒錯」≠「播得出來」)。正確做法:
1. 用 concat **filter**(`-filter_complex ... concat=n=N:v=1:a=1`)重新編碼成
   單一連續串流
2. 每個輸入先正規化:`scale=1920:1080,setsar=1,fps=30,format=yuv420p` +
   音訊統一 `48000Hz`(取樣率不一致會在切換點爆音或卡死)
3. 音訊一律重編碼(`-c:a aac -b:a 192k`),不要 `-c:a copy`
4. TTS 旁白(約 -25 LUFS)與外部素材(約 -16)響度差近 10dB,旁白片段過
   `loudnorm=I=-16:TP=-1.5:LRA=11` 對齊,不然觀眾會被嚇到
5. 最後加 `-movflags +faststart`

(同一來源、都由 `pipeline.py` 產生的片段,維持現有 concat demuxer 做法即可,
參數完全一致所以安全。)
