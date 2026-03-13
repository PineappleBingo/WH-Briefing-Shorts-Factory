"""
Content Production — convert grouped expressions to clip definitions.
Usage: python pipeline/expressions_to_clips.py --in data/expressions_grouped.json --out data/clips.json

Transforms expression groups into timed clip sequences with:
  - Hook segment (3s)
  - Expression segments (original video timestamps)
  - Freeze frame segments (3s each, for Korean explanation)
  - Wrapup segment (5s)
"""

import argparse
import json
import os
import sys

# Segment durations in seconds
HOOK_DURATION = 3.0
FREEZE_FRAME_DURATION = 3.0
WRAPUP_DURATION = 5.0
MAX_SHORT_DURATION = 180.0


def build_clips_for_group(group: dict) -> dict:
    """Convert a single expression group into a timed clip sequence."""
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

    # 2. Expression + freeze_frame pairs
    for expr in group["expressions"]:
        # Calculate expression segment duration from original timestamps
        original_duration = expr["end"] - expr["start"]
        # Clamp to reasonable bounds: at least 3s, at most 20s
        expr_duration = max(3.0, min(20.0, original_duration))

        # Check if adding this expression would exceed max duration
        needed = expr_duration + FREEZE_FRAME_DURATION
        if cursor + needed + WRAPUP_DURATION > MAX_SHORT_DURATION:
            break

        # Expression segment (playing original video)
        clips.append({
            "start": round(cursor, 3),
            "end": round(cursor + expr_duration, 3),
            "type": "expression",
            "overlay": {
                "en": expr["expression"],
                "kr": expr["explanation_kr"],
            },
            "highlightColor": expr.get("highlight_color", "#00BFFF"),
            # Store original timestamps for video sourcing
            "_source_start": expr["start"],
            "_source_end": expr["end"],
        })
        cursor += expr_duration

        # Freeze frame segment (Korean explanation overlay)
        clips.append({
            "start": round(cursor, 3),
            "end": round(cursor + FREEZE_FRAME_DURATION, 3),
            "type": "freeze_frame",
            "overlay": {
                "en": expr["definition_en"],
                "kr": expr["explanation_kr"],
            },
        })
        cursor += FREEZE_FRAME_DURATION

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
        expr_count = sum(1 for c in part["clips"] if c["type"] == "expression")
        print(f"    {part['id']}: {expr_count} expressions, {total_duration:.1f}s total")

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
