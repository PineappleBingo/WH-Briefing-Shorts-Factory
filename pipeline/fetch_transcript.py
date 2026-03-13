"""
Sourcing Module — fetch video captions via yt-dlp.
Usage: python pipeline/fetch_transcript.py --url <YOUTUBE_URL> --out data/transcript.json

Reads VTT caption files downloaded by yt-dlp, deduplicates overlapping cues,
strips word-level timing tags, and outputs a cleaned JSON transcript.
"""

import argparse
import glob
import html
import json
import os
import re
import subprocess
import sys


def parse_timestamp(ts: str) -> float:
    """Convert HH:MM:SS.mmm or MM:SS.mmm to seconds."""
    parts = ts.strip().split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return 0.0


def clean_line(text: str) -> str:
    """Strip VTT formatting tags, HTML entities, and speaker markers."""
    # Remove word-level timing tags: <00:00:03.840>
    text = re.sub(r"<[\d:.]+>", "", text)
    # Remove <c> and </c> tags
    text = re.sub(r"</?c>", "", text)
    # Decode HTML entities (&gt;&gt; → >>)
    text = html.unescape(text)
    # Remove speaker markers (>> )
    text = re.sub(r"^>>\s*", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_vtt(vtt_path: str) -> list[dict]:
    """Parse a VTT file into deduplicated, cleaned cues."""
    with open(vtt_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split into cue blocks (separated by blank lines)
    blocks = re.split(r"\n\s*\n", content)

    cues = []
    seen_texts = set()

    for block in blocks:
        lines = block.strip().split("\n")

        # Find the timestamp line
        ts_line = None
        text_lines = []
        for line in lines:
            if "-->" in line:
                ts_line = line
            elif ts_line is not None:
                text_lines.append(line)

        if not ts_line or not text_lines:
            continue

        # Parse start/end timestamps (ignore positioning after timestamps)
        ts_match = re.match(r"([\d:.]+)\s*-->\s*([\d:.]+)", ts_line)
        if not ts_match:
            continue

        start = parse_timestamp(ts_match.group(1))
        end = parse_timestamp(ts_match.group(2))

        # Clean and join text lines
        cleaned = " ".join(clean_line(line) for line in text_lines)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # Skip empty or whitespace-only cues
        if not cleaned:
            continue

        # Deduplicate: YouTube VTT shows overlapping 2-line cues
        # Skip if we've seen this exact text recently
        if cleaned in seen_texts:
            continue
        seen_texts.add(cleaned)

        # Limit seen_texts to avoid memory issues on very long videos
        if len(seen_texts) > 500:
            seen_texts = set(list(seen_texts)[-250:])

        cues.append({
            "start": round(start, 3),
            "end": round(end, 3),
            "text": cleaned,
        })

    return cues


def merge_into_sentences(cues: list[dict]) -> list[dict]:
    """Merge short cues into full sentences based on punctuation boundaries."""
    if not cues:
        return []

    sentences = []
    buffer_text = ""
    buffer_start = cues[0]["start"]
    buffer_end = cues[0]["end"]

    for cue in cues:
        if not buffer_text:
            buffer_start = cue["start"]

        buffer_text = (buffer_text + " " + cue["text"]).strip()
        buffer_end = cue["end"]

        # Split on sentence-ending punctuation
        if re.search(r"[.!?]$", buffer_text):
            sentences.append({
                "text": buffer_text,
                "start": round(buffer_start, 3),
                "end": round(buffer_end, 3),
            })
            buffer_text = ""

    # Flush remaining buffer
    if buffer_text.strip():
        sentences.append({
            "text": buffer_text.strip(),
            "start": round(buffer_start, 3),
            "end": round(buffer_end, 3),
        })

    return sentences


def find_vtt_file(data_dir: str) -> str | None:
    """Find the most recent .vtt file in data directory."""
    patterns = [
        os.path.join(data_dir, "*.en.vtt"),
        os.path.join(data_dir, "**", "*.en.vtt"),
        os.path.join(data_dir, "*.vtt"),
    ]
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            # Return the most recently modified
            return max(matches, key=os.path.getmtime)
    return None


def get_video_metadata(url: str) -> dict:
    """Fetch video title and duration via yt-dlp --print."""
    meta = {"title": "", "duration": 0}
    try:
        result = subprocess.run(
            ["yt-dlp", "--no-playlist", "--print", "%(title)s\n%(duration)s", url],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if len(lines) >= 2:
                meta["title"] = lines[0]
                meta["duration"] = int(lines[1])
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    return meta


def main():
    parser = argparse.ArgumentParser(description="Parse yt-dlp VTT captions into transcript JSON")
    parser.add_argument("--url", required=True, help="YouTube video URL")
    parser.add_argument("--out", required=True, help="Output JSON path")
    args = parser.parse_args()

    data_dir = os.path.dirname(args.out) or "data"

    # Find VTT file
    vtt_path = find_vtt_file(data_dir)
    if not vtt_path:
        print(f"ERROR: No .vtt file found in {data_dir}/", file=sys.stderr)
        print("  Make sure yt-dlp downloaded captions first:", file=sys.stderr)
        print(f'  yt-dlp --no-playlist --write-auto-sub --sub-lang en --skip-download -o "{data_dir}/%(title)s" "{args.url}"', file=sys.stderr)
        sys.exit(1)

    print(f"  Parsing VTT: {vtt_path}")

    # Parse and clean
    cues = parse_vtt(vtt_path)
    print(f"  Raw cues after dedup: {len(cues)}")

    sentences = merge_into_sentences(cues)
    print(f"  Merged sentences: {len(sentences)}")

    # Fetch metadata
    meta = get_video_metadata(args.url)

    # Build output
    transcript = {
        "title": meta["title"],
        "duration": meta["duration"],
        "source_url": args.url,
        "sentences": sentences,
    }

    # Write output
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(transcript, f, indent=2, ensure_ascii=False)

    print(f"  Output: {args.out} ({len(sentences)} sentences)")


if __name__ == "__main__":
    main()
