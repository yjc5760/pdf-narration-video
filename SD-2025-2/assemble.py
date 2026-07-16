#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""讀取 work/page-NN.json 快取,串接所有片段成最終影片,並產生對應 SRT。"""
import json
import re
from pipeline import (WORK_DIR, OUTPUT_DIR, concat_clips, build_page_srt_entries,
                      write_srt, _probe_duration)

cache_files = sorted(WORK_DIR.glob("page-*.json"))
if not cache_files:
    raise SystemExit("work/ 裡沒有 page-NN.json 快取,請先跑 process_pages.py 或 pipeline.py")

page_nums = sorted(int(re.search(r"page-(\d+)", p.stem).group(1)) for p in cache_files)

clip_paths = []
for n in page_nums:
    clip = WORK_DIR / f"clip-{n:02d}.mp4"
    if not clip.exists():
        raise SystemExit(f"缺少片段 {clip.name},頁 {n} 還沒處理完")
    clip_paths.append(clip)

print("串接所有片段中...")
final_video = OUTPUT_DIR / "final_video.mp4"
concat_clips(clip_paths, final_video)

all_entries = []
time_cursor = 0.0
for n, clip in zip(page_nums, clip_paths):
    info = json.loads((WORK_DIR / f"page-{n:02d}.json").read_text(encoding="utf-8"))
    entries = build_page_srt_entries(
        info["text"], time_cursor, info["duration"],
        [tuple(t) for t in info.get("word_timestamps", [])],
    )
    all_entries.extend(entries)
    # 用片段實際長度(含頁尾靜音)推進時間軸,與 pipeline.py 一致
    time_cursor += _probe_duration(clip)

final_srt = OUTPUT_DIR / "final_video.srt"
write_srt(all_entries, final_srt)

print(f"完成!\n影片: {final_video}\n字幕: {final_srt}\n總長度: {time_cursor:.1f} 秒")
