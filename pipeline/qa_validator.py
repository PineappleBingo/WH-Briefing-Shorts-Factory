"""
QA & Automation Module — validate clips and auto-fix issues.
Usage: python pipeline/qa_validator.py --in data/clips.json --out data/qa_report.json

Rules:
  - Subtitle: max 2 lines, max 42 chars/line
  - Clip duration: <= 180 seconds
  - No temporal overlap between clips within a part
  - Auto-fix: line-break at 42 chars, trim to 180s
"""

import argparse
import json
import os
import sys
import textwrap

MAX_LINES = 2
MAX_CHARS_PER_LINE = 42
MAX_DURATION = 180.0


def wrap_text(text: str, max_chars: int = MAX_CHARS_PER_LINE, max_lines: int = MAX_LINES) -> str:
    """Wrap text to fit within max_chars per line, max_lines total."""
    if len(text) <= max_chars:
        return text

    wrapped = textwrap.wrap(text, width=max_chars)
    if len(wrapped) > max_lines:
        wrapped = wrapped[:max_lines]
        # Truncate last line if needed
        if len(wrapped[-1]) > max_chars:
            wrapped[-1] = wrapped[-1][:max_chars - 3] + "..."

    return "\n".join(wrapped)


def validate_overlay_text(overlay: dict, clip_index: int, part_id: str) -> list[dict]:
    """Validate overlay text fields and return issues found."""
    issues = []

    for lang in ("en", "kr"):
        text = overlay.get(lang, "")
        if not text:
            continue

        lines = text.split("\n")

        # Check line count
        if len(lines) > MAX_LINES:
            issues.append({
                "part": part_id,
                "clip": clip_index,
                "field": f"overlay.{lang}",
                "rule": "max_lines",
                "detail": f"{len(lines)} lines (max {MAX_LINES})",
                "auto_fixed": True,
            })

        # Check chars per line
        for i, line in enumerate(lines):
            if len(line) > MAX_CHARS_PER_LINE:
                issues.append({
                    "part": part_id,
                    "clip": clip_index,
                    "field": f"overlay.{lang}[{i}]",
                    "rule": "max_chars_per_line",
                    "detail": f"{len(line)} chars (max {MAX_CHARS_PER_LINE})",
                    "auto_fixed": True,
                })

    return issues


def validate_and_fix_part(part: dict) -> tuple[dict, list[dict]]:
    """Validate a single part's clips and auto-fix issues. Returns (fixed_part, issues)."""
    issues = []
    fixed_clips = []
    part_id = part["id"]

    # Calculate total duration
    if part["clips"]:
        total_duration = part["clips"][-1]["end"]
    else:
        total_duration = 0

    # Check total duration
    if total_duration > MAX_DURATION:
        issues.append({
            "part": part_id,
            "clip": -1,
            "field": "duration",
            "rule": "max_duration",
            "detail": f"{total_duration:.1f}s (max {MAX_DURATION}s)",
            "auto_fixed": True,
        })

    prev_end = 0.0
    for i, clip in enumerate(part["clips"]):
        fixed_clip = dict(clip)

        # Check for temporal overlap
        if clip["start"] < prev_end - 0.001:  # small epsilon for float comparison
            issues.append({
                "part": part_id,
                "clip": i,
                "field": "timing",
                "rule": "no_overlap",
                "detail": f"clip starts at {clip['start']:.3f}s but previous ends at {prev_end:.3f}s",
                "auto_fixed": True,
            })
            fixed_clip["start"] = round(prev_end, 3)

        # Trim clips that exceed max duration
        if fixed_clip["end"] > MAX_DURATION:
            fixed_clip["end"] = MAX_DURATION
            issues.append({
                "part": part_id,
                "clip": i,
                "field": "end",
                "rule": "max_duration",
                "detail": f"trimmed to {MAX_DURATION}s",
                "auto_fixed": True,
            })

        # Skip clips that start after max duration
        if fixed_clip["start"] >= MAX_DURATION:
            issues.append({
                "part": part_id,
                "clip": i,
                "field": "start",
                "rule": "max_duration",
                "detail": f"clip starts at {fixed_clip['start']:.1f}s, dropped",
                "auto_fixed": True,
            })
            continue

        # Validate and fix overlay text
        if "overlay" in fixed_clip:
            text_issues = validate_overlay_text(fixed_clip["overlay"], i, part_id)
            issues.extend(text_issues)

            # Apply text fixes
            for lang in ("en", "kr"):
                if lang in fixed_clip["overlay"]:
                    fixed_clip["overlay"][lang] = wrap_text(fixed_clip["overlay"][lang])

        # Remove internal-only fields (prefixed with _)
        fixed_clip = {k: v for k, v in fixed_clip.items() if not k.startswith("_")}

        fixed_clips.append(fixed_clip)
        prev_end = fixed_clip["end"]

    return {"id": part_id, "clips": fixed_clips}, issues


def main():
    parser = argparse.ArgumentParser(description="Validate and auto-fix clip definitions")
    parser.add_argument("--in", dest="input", required=True, help="Input clips.json")
    parser.add_argument("--out", required=True, help="Output qa_report.json")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    parts = data.get("parts", [])
    if not parts:
        print("ERROR: No parts found in clips.json", file=sys.stderr)
        sys.exit(1)

    print(f"  Validating {len(parts)} parts...")

    all_issues = []
    fixed_parts = []
    has_fixes = False

    for part in parts:
        fixed_part, issues = validate_and_fix_part(part)
        fixed_parts.append(fixed_part)
        all_issues.extend(issues)
        if issues:
            has_fixes = True

    # Write QA report
    report = {
        "total_issues": len(all_issues),
        "all_passed": len(all_issues) == 0,
        "issues": all_issues,
    }

    report_dir = os.path.dirname(args.out) or "."
    os.makedirs(report_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"  Issues found: {len(all_issues)}")

    # Write fixed clips if any issues were found
    if has_fixes:
        fixed_path = os.path.join(report_dir, "clips_fixed.json")
        with open(fixed_path, "w", encoding="utf-8") as f:
            json.dump({"parts": fixed_parts}, f, indent=2, ensure_ascii=False)
        print(f"  Fixed clips: {fixed_path}")
    else:
        print("  All clips passed validation — no fixes needed")

    # Print summary
    for part in fixed_parts:
        clip_count = len(part["clips"])
        duration = part["clips"][-1]["end"] if part["clips"] else 0
        part_issues = sum(1 for i in all_issues if i["part"] == part["id"])
        status = "PASS" if part_issues == 0 else f"{part_issues} fixes"
        print(f"    {part['id']}: {clip_count} clips, {duration:.1f}s, {status}")


if __name__ == "__main__":
    main()
