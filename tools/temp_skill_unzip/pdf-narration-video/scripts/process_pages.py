#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分批處理頁面(避免單次執行超時)。

用法:
    python process_pages.py 1 5 --engine azure
    python process_pages.py 6 10 --engine azure
    ...全部批次跑完後執行 assemble.py 串接。

註:pipeline.py 現在內建每頁快取與 --pages 參數,
   `python pipeline.py --engine azure --pages 1-5` 效果相同,本檔保留向下相容。
結果(講稿、時長、時間戳)寫入 work/page-NN.json 快取,與 pipeline.py 共用。
"""
import argparse
from pipeline import (parse_narration, find_image, NARRATION_MD, WORK_DIR, OUTPUT_DIR,
                      ENGINES, AUDIO_EXT, build_page_clip,
                      load_page_cache, save_page_cache)

parser = argparse.ArgumentParser()
parser.add_argument("start_page", type=int)
parser.add_argument("end_page", type=int)
parser.add_argument("--engine", choices=ENGINES.keys(), default="espeak")
parser.add_argument("--force", action="store_true")
args = parser.parse_args()

WORK_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

synth_fn = ENGINES[args.engine]
audio_ext = AUDIO_EXT[args.engine]

pages = parse_narration(NARRATION_MD)

for page_num in range(args.start_page, args.end_page + 1):
    if page_num not in pages:
        continue
    text = pages[page_num]
    image_path = find_image(page_num)
    if image_path is None:
        raise SystemExit(f"[頁 {page_num}] 找不到對應圖片,先中止(避免浪費 TTS 額度)")
    audio_path = WORK_DIR / f"page-{page_num:02d}{audio_ext}"
    clip_path = WORK_DIR / f"clip-{page_num:02d}.mp4"

    result = None if args.force else load_page_cache(page_num, text, args.engine, audio_path)
    if result is not None:
        print(f"[頁 {page_num}] 使用快取(時長 {result.duration:.2f}s)")
    else:
        print(f"[頁 {page_num}] TTS...")
        result = synth_fn(text, audio_path)
        save_page_cache(page_num, text, args.engine, result)

    if args.force or not clip_path.exists():
        print(f"[頁 {page_num}] 建立影片片段 (時長 {result.duration:.2f}s)...")
        build_page_clip(image_path, audio_path, clip_path, result.duration)
    print(f"[頁 {page_num}] 完成")

print("批次完成,快取已更新(work/page-NN.json)")
