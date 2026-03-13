"""
Subtitle generator — convert clips.json to SRT format.
Usage: python pipeline/generate_srt.py --in data/clips.json --out output/part1/subtitles.srt

Generates bilingual EN+KR SRT subtitles from clip definitions.
Each clip becomes one SRT entry with both languages.
"""

import argparse
import json
import os
import sys


def seconds_to_srt_time(seconds: float) -> str:
    """Convert seconds to SRT timestamp format: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def clip_to_srt_entry(index: int, clip: dict) -> str:
    """Convert a single clip to an SRT subtitle entry."""
    start = seconds_to_srt_time(clip["start"])
    end = seconds_to_srt_time(clip["end"])

    overlay = clip.get("overlay", {})
    en = overlay.get("en", "").replace("\n", " ")
    kr = overlay.get("kr", "").replace("\n", " ")

    # Bilingual: EN on top, KR below
    text_lines = []
    if en:
        text_lines.append(en)
    if kr:
        text_lines.append(kr)

    text = "\n".join(text_lines)

    return f"{index}\n{start} --> {end}\n{text}\n"


def generate_srt(clips_data: dict, part_id: str | None = None) -> str:
    """Generate SRT content for a specific part or all parts."""
    entries = []
    index = 1

    for part in clips_data.get("parts", []):
        if part_id and part["id"] != part_id:
            continue

        for clip in part["clips"]:
            entries.append(clip_to_srt_entry(index, clip))
            index += 1

    return "\n".join(entries)


def main():
    parser = argparse.ArgumentParser(description="Generate SRT subtitles from clips JSON")
    parser.add_argument("--in", dest="input", required=True, help="Input clips JSON")
    parser.add_argument("--out", required=True, help="Output SRT file path")
    parser.add_argument("--part", default=None, help="Generate for specific part ID only")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        clips_data = json.load(f)

    parts = clips_data.get("parts", [])
    if not parts:
        print("ERROR: No parts found in input", file=sys.stderr)
        sys.exit(1)

    srt_content = generate_srt(clips_data, args.part)

    if not srt_content.strip():
        print("ERROR: No subtitle entries generated", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(srt_content)

    entry_count = srt_content.count("\n\n")
    target = f"part={args.part}" if args.part else "all parts"
    print(f"  Output: {args.out} ({entry_count} entries, {target})")


if __name__ == "__main__":
    main()
