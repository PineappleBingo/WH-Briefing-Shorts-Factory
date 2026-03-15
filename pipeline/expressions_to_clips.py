"""
Content Production — convert grouped expressions to clip definitions.
Usage: python pipeline/expressions_to_clips.py --in data/expressions_grouped.json --out data/clips.json

Transforms expression groups into timed clip sequences using the 3-pass
repetition pattern per expression:
  1. expression_raw   — hear the expression naturally in context
  2. expression_blank  — replay with keyword blanked (cloze recall)
  3. expression_reveal — keyword highlighted + definition + Korean
"""

import argparse
import json
import os
import sys

# Segment durations in seconds
HOOK_DURATION = 3.0
RAW_DURATION = 5.0        # Pass 1: hear it naturally
BLANK_DURATION = 4.0      # Pass 2: try to recall
REVEAL_DURATION = 5.0     # Pass 3: full reveal with definition
WRAPUP_DURATION = 5.0
MAX_SHORT_DURATION = 180.0


def build_clips_for_group(group: dict) -> dict:
    """Convert a single expression group into a 3-pass clip sequence."""
    clips = []
    cursor = 0.0  # running clock for the Short

    # 1. Hook segment
    clips.append({
        "start": round(cursor, 3),
        "end": round(cursor + HOOK_DURATION, 3),
        "type": "hook",
        "overlay": group["hook"],
    })
    cursor += HOOK_DURATION

    # 2. Three passes per expression: raw → blank → reveal
    for expr in group["expressions"]:
        keyword = expr["expression"]
        original_sentence = expr["original_sentence"]
        highlight_color = expr.get("highlight_color", "#00BFFF")

        # Calculate how much time this expression needs
        needed = RAW_DURATION + BLANK_DURATION + REVEAL_DURATION
        if cursor + needed + WRAPUP_DURATION > MAX_SHORT_DURATION:
            break

        # Source video segment — all 3 passes replay the same clip
        video_src = "video/source.mp4"
        clip_start = expr.get("start", 0.0)
        clip_end = expr.get("end", clip_start + RAW_DURATION)

        # Pass 1: RAW — hear the expression naturally in context
        clips.append({
            "start": round(cursor, 3),
            "end": round(cursor + RAW_DURATION, 3),
            "type": "expression_raw",
            "overlay": {
                "en": original_sentence,
                "kr": "",
            },
            "keyword": keyword,
            "highlightColor": highlight_color,
            "videoSrc": video_src,
            "clipStartSec": round(clip_start, 3),
            "clipEndSec": round(clip_end, 3),
        })
        cursor += RAW_DURATION

        # Pass 2: BLANK — replay with keyword blanked out (cloze deletion)
        clips.append({
            "start": round(cursor, 3),
            "end": round(cursor + BLANK_DURATION, 3),
            "type": "expression_blank",
            "overlay": {
                "en": original_sentence,
                "kr": expr["explanation_kr"],
            },
            "keyword": keyword,
            "videoSrc": video_src,
            "clipStartSec": round(clip_start, 3),
            "clipEndSec": round(clip_end, 3),
        })
        cursor += BLANK_DURATION

        # Pass 3: REVEAL — keyword highlighted + definition + Korean
        clips.append({
            "start": round(cursor, 3),
            "end": round(cursor + REVEAL_DURATION, 3),
            "type": "expression_reveal",
            "overlay": {
                "en": expr["definition_en"],
                "kr": expr["explanation_kr"],
            },
            "keyword": keyword,
            "highlightColor": highlight_color,
            "videoSrc": video_src,
            "clipStartSec": round(clip_start, 3),
            "clipEndSec": round(clip_end, 3),
        })
        cursor += REVEAL_DURATION

    # 3. Wrapup segment
    clips.append({
        "start": round(cursor, 3),
        "end": round(cursor + WRAPUP_DURATION, 3),
        "type": "wrapup",
        "overlay": group["closing"],
    })

    return {
        "id": group["group_id"],
        "clips": clips,
    }


def main():
    parser = argparse.ArgumentParser(description="Convert expression groups to clip definitions")
    parser.add_argument("--in", dest="input", required=True, help="Input expressions_grouped.json")
    parser.add_argument("--out", required=True, help="Output clips.json")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    groups = data.get("groups", [])
    if not groups:
        print("ERROR: No expression groups found", file=sys.stderr)
        sys.exit(1)

    print(f"  Processing {len(groups)} expression groups...")

    parts = []
    for group in groups:
        part = build_clips_for_group(group)
        total_duration = part["clips"][-1]["end"] if part["clips"] else 0
        expr_count = sum(1 for c in part["clips"] if c["type"] == "expression_raw")
        print(f"    {part['id']}: {expr_count} expressions x 3 passes, {total_duration:.1f}s total")

        if total_duration > MAX_SHORT_DURATION:
            print(f"    WARNING: {part['id']} exceeds {MAX_SHORT_DURATION}s — QA will trim", file=sys.stderr)

        parts.append(part)

    output = {"parts": parts}

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  Output: {args.out} ({len(parts)} parts)")


if __name__ == "__main__":
    main()
