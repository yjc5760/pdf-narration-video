#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# v2:加入 [[顯示|朗讀]] 語法、--verify ASR 回驗、faststart、品質三檢
"""
簡報轉影片 Pipeline
===================
腳本 → TTS(含時間戳)→ SRT字幕 → FFmpeg 合成影片

使用方式:
    python pipeline.py --engine azure       # 正式配音(需 AZURE_SPEECH_KEY / AZURE_SPEECH_REGION)
    python pipeline.py --engine elevenlabs  # 正式配音(需 ELEVENLABS_API_KEY)
    python pipeline.py --engine espeak      # 離線示範(免金鑰,驗證流程用)
    python pipeline.py --engine azure --force   # 忽略快取,全部重新合成
    python pipeline.py --engine azure --verify  # 加 ASR 發音回驗(同一組 Azure 金鑰)

講稿支援 [[顯示|朗讀]] 語法:字幕顯示「4.5」、TTS 唸「四點五」→ 寫 [[4.5|四點五]]

目錄結構假設:
    images/slide-01.jpg ... slide-15.jpg   (PDF每頁圖片,pdftoppm產生)
    narration.md                           (逐頁講稿,格式見 parse_narration())
輸出:
    output/final_video.mp4
    output/final_video.srt

重跑行為:每頁 TTS 結果會快取在 work/page-NN.json,講稿沒改就不會重新
呼叫付費 TTS;改了某頁講稿只會重跑那一頁。
"""

import os
import re
import json
import subprocess
import argparse
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

BASE_DIR = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "images"
NARRATION_MD = BASE_DIR / "narration.md"
WORK_DIR = BASE_DIR / "work"
OUTPUT_DIR = BASE_DIR / "output"

FPS = 10                  # 靜態圖影片幀率(低幀率大幅加速編碼、縮小檔案)
PAGE_TAIL_SILENCE = 0.6   # 每頁結尾補的靜音秒數,讓頁與頁之間有喘息感

# 每種引擎實際輸出的音訊格式(azure 設定輸出 MP3,不要再存成 .wav 誤導)
AUDIO_EXT = {"espeak": ".wav", "azure": ".mp3", "elevenlabs": ".mp3"}


def _run(cmd):
    """執行外部指令;失敗時把 stderr 一起丟出來,不要吞掉錯誤訊息。"""
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(
            f"指令失敗 (exit {proc.returncode}): {' '.join(str(c) for c in cmd)}\n"
            f"--- stderr ---\n{proc.stderr[-2000:]}"
        )
    return proc


# ---------------------------------------------------------------------------
# 1. 解析逐頁講稿
# ---------------------------------------------------------------------------
def parse_narration(md_path: Path) -> dict:
    """
    解析格式如下的講稿檔:
        ## 頁 1 — 標題
        講稿內容...
        ---
    回傳 {頁碼: 講稿文字}
    """
    text = md_path.read_text(encoding="utf-8")
    pattern = r"## 頁\s*(\d+)\s*—.*?\n(.*?)(?=\n## 頁|\Z)"
    matches = re.findall(pattern, text, flags=re.S)
    pages = {}
    for num, body in matches:
        # 去除多餘的分隔線、空白
        cleaned = body.strip()
        cleaned = re.sub(r"\n-{3,}\n?", "", cleaned).strip()
        pages[int(num)] = cleaned
    return dict(sorted(pages.items()))


# 「顯示文|朗讀文」分離語法:講稿裡寫 [[4.5|四點五]] → 字幕顯示「4.5」,TTS 唸「四點五」。
# 用途:版本號、英文縮寫、TTS 老是唸錯的字(餵同音替身字,字幕仍顯示正確字)。
_TOKEN_RE = re.compile(r"\[\[([^|｜\]]*)[|｜]([^\]]*)\]\]")


def split_display_tts(raw: str):
    """把含 [[顯示|朗讀]] 標記的講稿拆成三份:
    segments:     [(顯示片段, 朗讀片段), ...](無標記處兩者相同)
    display_text: 字幕用文字
    tts_text:     送 TTS 的文字(時間戳都是對這份文字)
    """
    segments = []
    pos = 0
    for m in _TOKEN_RE.finditer(raw):
        if m.start() > pos:
            plain = raw[pos:m.start()]
            segments.append((plain, plain))
        segments.append((m.group(1), m.group(2)))
        pos = m.end()
    if pos < len(raw):
        plain = raw[pos:]
        segments.append((plain, plain))
    display_text = "".join(d for d, _ in segments)
    tts_text = "".join(t for _, t in segments)
    return segments, display_text, tts_text


def scan_heteronyms(pages: dict):
    """掃描講稿中的破音字高風險詞(heteronyms.json 存在才執行,僅提醒不阻擋)。
    Azure 對破音字通常判斷正確,ElevenLabs 風險較高;可搭配 --verify 實際確認。"""
    het_path = None
    for cand in (BASE_DIR / "heteronyms.json", BASE_DIR / "references" / "heteronyms.json"):
        if cand.exists():
            het_path = cand
            break
    if het_path is None:
        return
    try:
        data = json.loads(het_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    warns = []
    for ch, info in data.get("chars", {}).items():
        words = [w for w in info.get("rewrites", {}) if w] or (
            [ch] if info.get("status") == "confirmed" else [])
        for w in words:
            for n, raw in pages.items():
                _, _, tts_text = split_display_tts(raw)
                if w in tts_text:
                    warns.append(f"  頁 {n}: 「{w}」(破音字「{ch}」)")
    if warns:
        print("⚠ 破音字掃描(僅提醒;可改寫、用 [[顯示|朗讀]] 換同音字,或跑 --verify 確認發音):")
        for w in warns[:20]:
            print(w)
        if len(warns) > 20:
            print(f"  ...另有 {len(warns) - 20} 處")


def find_image(page_num: int) -> Path | None:
    """找該頁對應的圖片。pdftoppm 依總頁數決定補零位數(<100頁兩位數,
    >=100頁三位數),這裡各種位數都試,不寫死。"""
    for stem in (f"slide-{page_num:02d}", f"slide-{page_num:03d}", f"slide-{page_num}"):
        for ext in (".jpg", ".jpeg", ".png"):
            p = IMAGES_DIR / (stem + ext)
            if p.exists():
                return p
    return None


# ---------------------------------------------------------------------------
# 2. TTS 引擎(三選一)
# ---------------------------------------------------------------------------
class TTSResult:
    def __init__(self, audio_path, duration, word_timestamps=None):
        self.audio_path = audio_path
        self.duration = duration          # 秒
        self.word_timestamps = word_timestamps or []  # [(text_fragment, start_s, end_s), ...]


def synth_espeak(text: str, out_path: Path, lang="zh") -> TTSResult:
    """離線示範用,無逐字時間戳,只取得整段音檔長度。"""
    _run(["espeak-ng", "-v", lang, "-s", "155", text, "-w", str(out_path)])
    duration = _probe_duration(out_path)
    return TTSResult(out_path, duration)


def synth_azure(text: str, out_path: Path,
                voice="zh-TW-HsiaoChenNeural") -> TTSResult:
    """
    正式配音:Azure TTS,含 word boundary 時間戳。
    需要環境變數 AZURE_SPEECH_KEY / AZURE_SPEECH_REGION。
    pip install azure-cognitiveservices-speech
    """
    import azure.cognitiveservices.speech as speechsdk

    key = os.environ["AZURE_SPEECH_KEY"]
    region = os.environ["AZURE_SPEECH_REGION"]
    speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    speech_config.speech_synthesis_voice_name = voice
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio48Khz192KBitRateMonoMp3
    )
    audio_config = speechsdk.audio.AudioOutputConfig(filename=str(out_path))
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=audio_config
    )

    word_timestamps = []

    def on_word_boundary(evt):
        start_s = evt.audio_offset / 1e7  # 100ns units -> 秒
        dur_s = evt.duration.total_seconds()
        word_timestamps.append((evt.text, start_s, start_s + dur_s))

    synthesizer.synthesis_word_boundary.connect(on_word_boundary)

    # 講稿若含 & < > 等字元,不 escape 會讓 SSML 解析直接失敗
    ssml = (
        f'<speak version="1.0" xml:lang="zh-TW">'
        f'<voice name="{voice}">{xml_escape(text)}</voice></speak>'
    )
    result = synthesizer.speak_ssml_async(ssml).get()
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        detail = ""
        if result.reason == speechsdk.ResultReason.Canceled:
            detail = f" — {result.cancellation_details.error_details}"
        raise RuntimeError(f"Azure TTS 失敗: {result.reason}{detail}")

    duration = _probe_duration(out_path)
    return TTSResult(out_path, duration, word_timestamps)


def synth_elevenlabs(text: str, out_path: Path,
                      voice_id="21m00Tcm4TlvDq8ikWAM") -> TTSResult:
    """
    正式配音:ElevenLabs,含字元級時間戳。
    需要環境變數 ELEVENLABS_API_KEY。
    """
    import requests, base64

    api_key = os.environ["ELEVENLABS_API_KEY"]
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    payload = {"text": text, "model_id": "eleven_multilingual_v2"}

    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    audio_bytes = base64.b64decode(data["audio_base64"])
    out_path.write_bytes(audio_bytes)

    chars = data["alignment"]["characters"]
    starts = data["alignment"]["character_start_times_seconds"]
    ends = data["alignment"]["character_end_times_seconds"]
    word_timestamps = list(zip(chars, starts, ends))

    duration = _probe_duration(out_path)
    return TTSResult(out_path, duration, word_timestamps)


def _probe_duration(path: Path) -> float:
    out = _run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
    )
    return float(out.stdout.strip())


ENGINES = {"espeak": synth_espeak, "azure": synth_azure, "elevenlabs": synth_elevenlabs}


# ---------------------------------------------------------------------------
# 3. SRT 產生
# ---------------------------------------------------------------------------
def srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# 全形+半形都要涵蓋:講稿實際用的是全形 ，！？,漏掉會導致斷句失效、
# 對齊時 else 分支誤吃時間戳造成字幕偏移
_PUNCT_CHARS = "。，、！？；：,!?;:"
_SPLIT_RE = re.compile(f"(?<=[{_PUNCT_CHARS}])")


def _expand_word_times(word_timestamps):
    """
    把「逐詞」時間戳(如 Azure word boundary,一個事件可能對應多個字)
    展開成「逐字」時間戳,詞內時間用等分內插估計。
    ElevenLabs 的逐字時間戳(每個 entry 本來就是單一字元)展開後不受影響。
    """
    flat = []
    for word_text, w_start, w_end in word_timestamps:
        n = len(word_text)
        if n == 0:
            continue
        dur = (w_end - w_start) / n
        for i, ch in enumerate(word_text):
            flat.append((ch, w_start + i * dur, w_start + (i + 1) * dur))
    return flat


def _align_char_times(text: str, word_timestamps):
    """
    將展開後的逐字時間戳,對齊回與 text 完全等長的逐字時間戳列表。
    標點符號等沒有出現在語音時間戳裡的字元,時間戳沿用前一個字的結束時間
    (在文字開頭則用下一個字的開始時間),避免因為索引位移導致整段字幕錯位。
    """
    flat = _expand_word_times(word_timestamps)
    result = []
    fi = 0
    for ch in text:
        if fi < len(flat) and flat[fi][0] == ch:
            result.append(flat[fi])
            fi += 1
        elif ch in _PUNCT_CHARS or ch.isspace():
            t = result[-1][2] if result else (flat[fi][1] if fi < len(flat) else 0.0)
            result.append((ch, t, t))
        else:
            # 內容對不上的極少數情況:盡量往前吃一個時間戳,避免整段位移擴大
            if fi < len(flat):
                result.append(flat[fi])
                fi += 1
            else:
                t = result[-1][2] if result else 0.0
                result.append((ch, t, t))
    return result


def _display_char_times(segments, tts_char_times):
    """把「與 TTS 文字等長」的逐字時間戳,轉成「與顯示文字等長」的逐字時間戳。
    無標記片段 1:1 對應;[[顯示|朗讀]] 片段把朗讀時段等分攤給顯示字元。"""
    times = []
    ti = 0
    for disp, tts in segments:
        seg = tts_char_times[ti:ti + len(tts)]
        ti += len(tts)
        if disp == tts:
            times.extend(seg)
            continue
        if seg:
            start, end = seg[0][1], seg[-1][2]
        else:
            start = end = times[-1][2] if times else 0.0
        n = len(disp)
        if n:
            dur = (end - start) / n
            for i, ch in enumerate(disp):
                times.append((ch, start + i * dur, start + (i + 1) * dur))
    return times


def _split_spans(text: str, max_chars: int):
    """
    把整頁文字切成字幕條,回傳 [(start_idx, end_idx, 顯示文字), ...]。
    索引是「相對原始 text」的絕對位置,這樣後面切 char_times 不會因為
    strip 掉空白/換行而累積位移。
    先依標點切,超過 max_chars 的長句再等分二次拆分。
    """
    spans = []
    pos = 0
    for raw in _SPLIT_RE.split(text):
        if not raw:
            continue
        start, end = pos, pos + len(raw)
        pos = end
        core = raw.strip()
        if not core:
            continue
        s = start + (len(raw) - len(raw.lstrip()))
        e = end - (len(raw) - len(raw.rstrip()))
        if (e - s) <= max_chars:
            spans.append((s, e, text[s:e]))
        else:
            # 長句等分拆成每段 <= max_chars
            n = e - s
            pieces = -(-n // max_chars)          # ceil
            size = -(-n // pieces)               # ceil,讓各段長度平均
            for i in range(s, e, size):
                j = min(i + size, e)
                spans.append((i, j, text[i:j]))
    return spans


def build_page_srt_entries(text: str, offset: float, duration: float,
                            word_timestamps=None, max_chars=22):
    """
    有逐字時間戳就用時間戳精準切;沒有(如 espeak demo)則按字數比例
    平均分配時間,確保示範也有可讀的分段字幕。
    text 可含 [[顯示|朗讀]] 標記:字幕一律用顯示文,時間戳先對齊朗讀文再映射回顯示文。
    """
    segments, display_text, tts_text = split_display_tts(text)
    entries = []
    spans = _split_spans(display_text, max_chars)
    if not spans:
        return entries

    if word_timestamps:
        # 有精準時間戳:對齊朗讀文的逐字時間戳,再映射成顯示文的逐字時間戳,依 span 索引切
        char_times = _display_char_times(
            segments, _align_char_times(tts_text, word_timestamps))
        for s, e, disp in spans:
            seg = char_times[s:e]
            if not seg:
                continue
            entries.append((offset + seg[0][1], offset + seg[-1][2], disp))
    else:
        # 沒有時間戳:按字數比例切割整段 duration
        total_chars = sum(e - s for s, e, _ in spans)
        cursor_time = offset
        for s, e, disp in spans:
            portion = duration * ((e - s) / total_chars)
            entries.append((cursor_time, cursor_time + portion, disp))
            cursor_time += portion

    return entries


def write_srt(all_entries, out_path: Path):
    lines = []
    for i, (start, end, text) in enumerate(all_entries, 1):
        lines.append(str(i))
        lines.append(f"{srt_timestamp(start)} --> {srt_timestamp(end)}")
        lines.append(text)
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# 4. FFmpeg 影片合成(逐頁圖片+音頻 → 串接)
# ---------------------------------------------------------------------------
def build_page_clip(image_path: Path, audio_path: Path, out_clip: Path,
                    audio_duration: float):
    """圖片(靜態)+ 該頁音頻 → 該頁的影片片段。
    片段長度 = 音頻長度 + PAGE_TAIL_SILENCE(頁間喘息),用 -t 明確指定。"""
    total = audio_duration + PAGE_TAIL_SILENCE
    _run([
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", str(FPS), "-i", str(image_path),
        "-i", str(audio_path),
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "1",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
               "pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        "-af", f"apad=pad_dur={PAGE_TAIL_SILENCE}",
        "-r", str(FPS),
        "-t", f"{total:.3f}",
        str(out_clip),
    ])


def concat_clips(clip_paths, out_video: Path):
    concat_list = WORK_DIR / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for p in clip_paths:
            # ffmpeg concat 檔內用正斜線,避免 Windows 反斜線跳脫問題
            f.write(f"file '{p.resolve().as_posix()}'\n")
    _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list), "-c", "copy",
        # faststart:moov 移到檔頭,上傳網路/瀏覽器播放才能邊下邊播
        "-movflags", "+faststart",
        str(out_video),
    ])


def quality_check(video: Path, expected_duration: float):
    """產出後三檢:音訊 bitrate(抓無聲影片)、總長度、抽 frame 供目視比對。"""
    problems = []
    # 1. 音訊串流與 bitrate
    out = _run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                "-show_entries", "stream=codec_name,bit_rate",
                "-of", "default=noprint_wrappers=1", str(video)])
    info = out.stdout.strip()
    if "codec_name" not in info:
        problems.append("找不到音訊串流——影片可能是無聲的!")
    else:
        m = re.search(r"bit_rate=(\d+)", info)
        if m and int(m.group(1)) < 64000:
            problems.append(f"音訊 bitrate 僅 {int(m.group(1))//1000}kbps,可能近乎無聲(正常應約 192kbps)")
    # 2. 總長度
    actual = _probe_duration(video)
    if abs(actual - expected_duration) > 1.5:
        problems.append(f"影片長度 {actual:.1f}s 與預期 {expected_duration:.1f}s 差距過大")
    # 3. 抽一張 frame 供目視比對(確認用的是這批投影片,不是舊檔)
    frame = OUTPUT_DIR / "verify_frame.png"
    try:
        _run(["ffmpeg", "-y", "-ss", "3", "-i", str(video),
              "-frames:v", "1", "-update", "1", str(frame)])
        print(f"已抽出第 3 秒畫面: {frame} ——請目視確認與 images/slide-01 一致")
    except RuntimeError as e:
        problems.append(f"抽 frame 失敗: {e}")
    if problems:
        print("🔴 品質檢查發現問題:")
        for p in problems:
            print(f"  - {p}")
    else:
        print("✅ 品質檢查通過(音訊 bitrate / 總長度 / 抽 frame)")
    return problems


# ---------------------------------------------------------------------------
# 4.5 ASR 發音回驗(可選,--verify)
# 用 Azure STT(同一組 AZURE_SPEECH_KEY,不需額外金鑰)把合成音檔辨識回文字,
# 與講稿比對相似度,抓 TTS 唸錯的破音字/英文/數字。
# 判讀準則(重要,避免無限重試):
#   - 同音異字(報到↔報導)= ASR 誤報,音檔其實是對的 → 放行
#   - 多次合成「同一處、同一種錯」= TTS 真的唸錯 → 改寫該詞或用 [[顯示|朗讀]] 換同音字
#   - 有裝 pypinyin 時會加算「無聲調拼音相似度」,自動排除大部分同音字誤報
# ---------------------------------------------------------------------------
def _norm_for_compare(text: str) -> str:
    """去標點、空白、大小寫,只留內容字元供比對。"""
    return re.sub(r"[^\w]", "", text, flags=re.UNICODE).lower()


def _char_similarity(a: str, b: str) -> float:
    import difflib
    a, b = _norm_for_compare(a), _norm_for_compare(b)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _pinyin_similarity(a: str, b: str):
    """無聲調拼音多重集合相似度(需 pypinyin,沒裝回傳 None)。
    去掉數字再比——ASR 常把中文數字寫成阿拉伯數字,那不是唸錯。"""
    try:
        from pypinyin import lazy_pinyin
    except ImportError:
        return None
    from collections import Counter
    a2 = re.sub(r"\d", "", _norm_for_compare(a))
    b2 = re.sub(r"\d", "", _norm_for_compare(b))
    pa, pb = lazy_pinyin(a2), lazy_pinyin(b2)
    if not pa or not pb:
        return 0.0
    inter = sum((Counter(pa) & Counter(pb)).values())
    return inter / max(len(pa), len(pb))


def asr_transcribe_azure(audio_path: Path, duration: float) -> str:
    """Azure STT 連續辨識整段音檔。先用 ffmpeg 轉 16kHz 單聲道 WAV
    (SDK 原生只吃 WAV,直接餵 MP3 需要 GStreamer,別踩那個坑)。"""
    import threading
    import azure.cognitiveservices.speech as speechsdk

    key = os.environ["AZURE_SPEECH_KEY"]
    region = os.environ["AZURE_SPEECH_REGION"]
    wav_path = WORK_DIR / f"{audio_path.stem}-verify.wav"
    _run(["ffmpeg", "-y", "-i", str(audio_path),
          "-ar", "16000", "-ac", "1", str(wav_path)])

    speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    speech_config.speech_recognition_language = "zh-TW"
    audio_config = speechsdk.audio.AudioConfig(filename=str(wav_path))
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, audio_config=audio_config)

    parts = []
    done = threading.Event()
    recognizer.recognized.connect(lambda evt: parts.append(evt.result.text))
    recognizer.session_stopped.connect(lambda evt: done.set())
    recognizer.canceled.connect(lambda evt: done.set())
    recognizer.start_continuous_recognition()
    done.wait(timeout=max(60.0, duration * 3))  # 一定要有 timeout,不要無限等
    recognizer.stop_continuous_recognition()
    wav_path.unlink(missing_ok=True)
    return "".join(parts)


def verify_page(page_num: int, tts_text: str, audio_path: Path,
                duration: float, threshold: float) -> dict:
    """回驗單頁,結果快取在 work/verify-NN.json(講稿沒改就不重跑)。"""
    vp = WORK_DIR / f"verify-{page_num:02d}.json"
    if vp.exists():
        try:
            cached = json.loads(vp.read_text(encoding="utf-8"))
            if cached.get("tts_text") == tts_text:
                return cached
        except (json.JSONDecodeError, OSError):
            pass
    transcript = asr_transcribe_azure(audio_path, duration)
    char_sim = _char_similarity(tts_text, transcript)
    pin_sim = _pinyin_similarity(tts_text, transcript)
    # 字元相似度過門檻,或拼音相似度 >= 0.90(同音字誤報排除)即放行
    passed = char_sim >= threshold or (pin_sim is not None and pin_sim >= 0.90)
    result = {"page": page_num, "tts_text": tts_text, "transcript": transcript,
              "char_similarity": round(char_sim, 3),
              "pinyin_similarity": round(pin_sim, 3) if pin_sim is not None else None,
              "passed": passed}
    vp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def write_verify_report(results, out_path: Path, threshold: float):
    lines = [
        "# ASR 發音回驗報告", "",
        f"門檻:字元相似度 >= {threshold},或無聲調拼音相似度 >= 0.90", "",
        "| 頁 | 字元相似度 | 拼音相似度 | 結果 |",
        "|---|---|---|---|",
    ]
    for r in results:
        pin = r["pinyin_similarity"] if r["pinyin_similarity"] is not None else "—"
        lines.append(f"| {r['page']} | {r['char_similarity']} | {pin} | "
                     f"{'✅' if r['passed'] else '🔴 需人工聽'} |")
    fails = [r for r in results if not r["passed"]]
    if fails:
        lines += ["", "## 未通過頁面(先讀判讀準則,別急著重跑)", "",
                  "同音異字(如 報到↔報導)是 ASR 誤報,音檔是對的;",
                  "只有「關鍵詞/數字沒出現」或「多次合成同錯」才需要改講稿", ""]
        for r in fails:
            lines += [f"### 頁 {r['page']}", "",
                      f"- 講稿:{r['tts_text']}", f"- 辨識:{r['transcript']}", ""]
    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# 5. 每頁快取(講稿沒改就不重跑付費 TTS)
# ---------------------------------------------------------------------------
def _cache_path(page_num: int) -> Path:
    return WORK_DIR / f"page-{page_num:02d}.json"


def load_page_cache(page_num: int, text: str, engine: str, audio_path: Path):
    """講稿與引擎都沒變、音檔還在 → 回傳快取的 TTSResult,否則 None。"""
    cp = _cache_path(page_num)
    if not (cp.exists() and audio_path.exists()):
        return None
    try:
        data = json.loads(cp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("text") != text or data.get("engine") != engine:
        return None
    return TTSResult(audio_path, data["duration"],
                     [tuple(t) for t in data.get("word_timestamps", [])])


def save_page_cache(page_num: int, text: str, engine: str, result: TTSResult):
    _cache_path(page_num).write_text(
        json.dumps({
            "text": text,
            "engine": engine,
            "duration": result.duration,
            "word_timestamps": result.word_timestamps,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# 6. 主流程
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=ENGINES.keys(), default="espeak")
    parser.add_argument("--force", action="store_true",
                        help="忽略快取,全部重新 TTS 與合成")
    parser.add_argument("--pages", default=None,
                        help="只處理指定範圍,例如 3-7(仍會與快取中的其他頁一起串接)")
    parser.add_argument("--verify", action="store_true",
                        help="ASR 發音回驗:用 Azure STT 把合成音檔辨識回文字與講稿比對"
                             "(同一組 AZURE_SPEECH_KEY,不需額外金鑰)")
    parser.add_argument("--verify-threshold", type=float, default=0.85,
                        help="回驗字元相似度門檻(預設 0.85)")
    args = parser.parse_args()

    WORK_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    pages = parse_narration(NARRATION_MD)
    print(f"解析到 {len(pages)} 頁講稿")
    if not pages:
        raise SystemExit("narration.md 沒有解析到任何頁,請檢查「## 頁 N — 標題」格式")
    scan_heteronyms(pages)

    # --- 前置檢查:先確認每頁都有圖,再開始花 TTS 額度 ---
    missing = [n for n in pages if find_image(n) is None]
    if missing:
        raise SystemExit(
            f"以下頁碼找不到對應圖片(images/slide-NN.jpg):{missing}\n"
            f"請先執行 pdftoppm 轉圖,或確認頁碼對應。"
        )
    extra = []
    for img in sorted(IMAGES_DIR.glob("slide-*")):
        m = re.search(r"slide-(\d+)", img.stem)
        if m and int(m.group(1)) not in pages:
            extra.append(img.name)
    if extra:
        print(f"提醒:這些圖片沒有對應講稿,將被跳過:{extra}")

    page_range = None
    if args.pages:
        a, _, b = args.pages.partition("-")
        page_range = range(int(a), int(b or a) + 1)

    synth_fn = ENGINES[args.engine]
    audio_ext = AUDIO_EXT[args.engine]

    clip_paths = []
    all_srt_entries = []
    verify_results = []
    time_cursor = 0.0

    for page_num, text in pages.items():
        image_path = find_image(page_num)
        audio_path = WORK_DIR / f"page-{page_num:02d}{audio_ext}"
        clip_path = WORK_DIR / f"clip-{page_num:02d}.mp4"
        # [[顯示|朗讀]] 分離:TTS 與時間戳用朗讀文,字幕用顯示文
        _, _, tts_text = split_display_tts(text)

        in_range = page_range is None or page_num in page_range

        result = None
        if not args.force:
            result = load_page_cache(page_num, text, args.engine, audio_path)

        if result is not None:
            print(f"[頁 {page_num}] 使用快取(時長 {result.duration:.2f}s)")
        elif in_range:
            print(f"[頁 {page_num}] TTS 合成中...")
            result = synth_fn(tts_text, audio_path)
            save_page_cache(page_num, text, args.engine, result)
        else:
            raise SystemExit(f"[頁 {page_num}] 不在 --pages 範圍內又沒有可用快取,無法串接完整影片")

        if args.verify:
            if args.engine == "azure":
                print(f"[頁 {page_num}] ASR 發音回驗中...")
                vr = verify_page(page_num, tts_text, audio_path,
                                 result.duration, args.verify_threshold)
                verify_results.append(vr)
                mark = "✅" if vr["passed"] else "🔴"
                print(f"[頁 {page_num}] {mark} 字元相似度 {vr['char_similarity']}"
                      + (f" / 拼音 {vr['pinyin_similarity']}"
                         if vr["pinyin_similarity"] is not None else ""))
            else:
                print(f"[頁 {page_num}] --verify 目前僅支援 azure 引擎,跳過")

        if args.force or not clip_path.exists():
            print(f"[頁 {page_num}] 合成影片片段(時長 {result.duration:.2f}s)...")
            build_page_clip(image_path, audio_path, clip_path, result.duration)
        clip_paths.append(clip_path)

        entries = build_page_srt_entries(
            text, time_cursor, result.duration, result.word_timestamps
        )
        all_srt_entries.extend(entries)
        # 用片段實際長度推進時間軸(含頁尾靜音),避免字幕越後面越提前
        time_cursor += _probe_duration(clip_path)

    print("串接所有片段...")
    final_video = OUTPUT_DIR / "final_video.mp4"
    concat_clips(clip_paths, final_video)

    final_srt = OUTPUT_DIR / "final_video.srt"
    write_srt(all_srt_entries, final_srt)

    quality_check(final_video, time_cursor)

    if verify_results:
        report = OUTPUT_DIR / "verify_report.md"
        write_verify_report(verify_results, report, args.verify_threshold)
        fails = sum(1 for r in verify_results if not r["passed"])
        print(f"發音回驗:{len(verify_results) - fails}/{len(verify_results)} 頁通過,"
              f"報告: {report}" + (f"(有 {fails} 頁需人工聽,見報告判讀準則)" if fails else ""))

    print(f"完成!\n影片: {final_video}\n字幕: {final_srt}\n總長度: {time_cursor:.1f} 秒")


if __name__ == "__main__":
    main()
