#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
簡報轉影片 Pipeline
===================
腳本 → TTS(含時間戳)→ SRT字幕 → FFmpeg 合成影片

使用方式:
    python pipeline.py --engine azure       # 正式配音(需 AZURE_SPEECH_KEY / AZURE_SPEECH_REGION)
    python pipeline.py --engine elevenlabs  # 正式配音(需 ELEVENLABS_API_KEY)
    python pipeline.py --engine espeak      # 離線示範(免金鑰,驗證流程用)
    python pipeline.py --engine azure --force   # 忽略快取,全部重新合成

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


def find_image(page_num: int):
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
    """
    entries = []
    spans = _split_spans(text, max_chars)
    if not spans:
        return entries

    if word_timestamps:
        # 有精準時間戳:展開並對齊回與原文等長的逐字時間戳,再依 span 索引切
        char_times = _align_char_times(text, word_timestamps)
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
        "-i", str(concat_list), "-c", "copy", str(out_video),
    ])


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
    args = parser.parse_args()

    WORK_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    pages = parse_narration(NARRATION_MD)
    print(f"解析到 {len(pages)} 頁講稿")
    if not pages:
        raise SystemExit("narration.md 沒有解析到任何頁,請檢查「## 頁 N — 標題」格式")

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
    time_cursor = 0.0

    for page_num, text in pages.items():
        image_path = find_image(page_num)
        audio_path = WORK_DIR / f"page-{page_num:02d}{audio_ext}"
        clip_path = WORK_DIR / f"clip-{page_num:02d}.mp4"

        in_range = page_range is None or page_num in page_range

        result = None
        if not args.force:
            result = load_page_cache(page_num, text, args.engine, audio_path)

        if result is not None:
            print(f"[頁 {page_num}] 使用快取(時長 {result.duration:.2f}s)")
        elif in_range:
            print(f"[頁 {page_num}] TTS 合成中...")
            result = synth_fn(text, audio_path)
            save_page_cache(page_num, text, args.engine, result)
        else:
            raise SystemExit(f"[頁 {page_num}] 不在 --pages 範圍內又沒有可用快取,無法串接完整影片")

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

    print(f"完成!\n影片: {final_video}\n字幕: {final_srt}\n總長度: {time_cursor:.1f} 秒")


if __name__ == "__main__":
    main()
