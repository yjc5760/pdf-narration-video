# Windows(cmd)常見卡關與排解

目標使用者多半是在 Windows 內建的「命令提示字元」(cmd.exe)操作,不是 bash 也不是
PowerShell。這件事很容易被忽略,因為多數技術文件範例都是 bash/PowerShell 語法,
直接照抄貼進 cmd 會報錯。

## 1. 不要給 bash/PowerShell 語法

錯誤示範(cmd 會直接報錯):
```
# 這是註解
export AZURE_SPEECH_KEY="xxx"
set -a; source .env; set +a; python3 pipeline.py --engine azure
```

cmd 沒有 `#` 註解語法、沒有 `export`、沒有 `source`。與其每次都解釋語法差異,更穩妥的
做法是包成 `.bat` 批次檔給使用者直接執行(見 `scripts/run_azure.bat`),使用者只要
輸入檔名就好,不用自己組指令。

`run_azure.bat` 的原理是用 `for /f` 讀取 `.env` 逐行設定環境變數(用 `%%~B` 去除
值兩側的引號),再呼叫 `python pipeline.py --engine azure`。

如果使用者問「我要怎麼手動設定環境變數」,cmd 語法是:
```
set AZURE_SPEECH_KEY=你的金鑰
set AZURE_SPEECH_REGION=southeastasia
```
（cmd 的 `set` 不需要引號包值,但如果值裡有特殊字元建議還是包一下）

## 2. ffmpeg/ffprobe 缺失,而且錯誤訊息會誤導人

`pipeline.py` 呼叫 Azure TTS 成功「之後」才會呼叫 `ffprobe` 量測音檔長度。如果
`ffprobe` 沒裝,錯誤會長這樣:

```
[頁 1] TTS 合成中...
Traceback (most recent call last):
  ...
FileNotFoundError: [WinError 2] 系統找不到指定的檔案。
```

**這個錯誤發生在 TTS 呼叫「之後」,代表金鑰跟網路都沒問題,只是缺 ffmpeg。**不要因為
看到 Traceback 就懷疑金鑰或程式碼邏輯,先確認 `ffprobe -version` 有沒有反應。

安裝:
```
winget install ffmpeg
```

**裝完一定要關掉目前的命令提示字元視窗、開一個新的**,PATH 環境變數的變更不會套用到
已經開著的視窗。如果新視窗還是抓不到,兩個備案:
1. 手動下載 https://www.gyan.dev/ffmpeg/builds/ 的 release essentials 版本,解壓縮後
   把 `bin` 資料夾裡的 `ffmpeg.exe`、`ffprobe.exe` 直接複製到專案資料夾(跟
   `pipeline.py` 同一層)——Windows 執行程式時會優先找目前資料夾,不用改 PATH
2. 如果使用者裝過 Chocolatey,`choco install ffmpeg -y` 也可以

## 3. 使用者可能忘記自己在哪個資料夾

`run_azure.bat` 必須在專案資料夾(有 `pipeline.py`、`.env`、`images/`、`narration.md`
的那個資料夾)裡執行。如果使用者的提示字元顯示在別的路徑(例如裝完 ffmpeg 後開新視窗
會回到 `C:\Users\使用者名稱>`),記得先請他們 `cd` 回專案資料夾。

## 4. 字幕方塊亂碼

`final_video.mp4` 沒有燒錄字幕,`.srt` 是外部檔案。使用者用某些播放器(內建的、或
不支援 UTF-8 中文字幕的播放器)開影片時,字幕可能顯示成方塊亂碼。這不是檔案壞掉,是
播放器字型/編碼問題。解法見 SKILL.md 主文的「字幕燒錄」段落。

## 5. 金鑰不要回顯、不要存進 memory

使用者貼金鑰給你時,直接寫進專案資料夾的 `.env`,不要在對話裡重複貼出金鑰內容
(即使只是為了確認),也不要把金鑰存進任何跨對話的記憶系統。
