# How to Run

## Prerequisites

| Tool | Version | Check Command | Purpose |
|---|---|---|---|
| Node.js | >= 18 | `node --version` | Remotion runtime |
| npm | >= 9 | `npm --version` | Package management |
| Python | >= 3.9 | `python3 --version` | Pipeline scripts |
| yt-dlp | latest | `yt-dlp --version` | Video/caption download |
| FFmpeg | >= 5.0 | `ffmpeg -version` | Fallback rendering, post-render verification |
| Chrome/Chromium | latest | — | Remotion uses headless Chrome for rendering |

---

## Quick Start (Automated)

The entire pipeline runs with a single command via `run_pipeline.sh`:

```bash
# 1. Clone & install
git clone https://github.com/PineappleBingo/WH-Briefing-Shorts-Factory.git
cd WH-Briefing-Shorts-Factory
npm install

# 2. Configure
cp .env.example .env
# Edit .env — set YT_VIDEO_URL and PERFORMANCE_MODE

# 3. Run the full pipeline
./run_pipeline.sh
```

### Usage & Options

```
./run_pipeline.sh [OPTIONS]

Options:
  --skip-render   Run data pipeline only (steps 0–6), skip video rendering
  --preview       Open Remotion Studio for visual preview before rendering
  -h, --help      Show help message
```

### Examples

```bash
# Full pipeline: fetch → analyze → render
./run_pipeline.sh

# Data pipeline only (no rendering) — useful during development
./run_pipeline.sh --skip-render

# Preview in Remotion Studio before rendering
./run_pipeline.sh --preview
```

### What the Script Does

| Step | Phase | What Happens |
|------|-------|-------------|
| 0 | Setup | Checks prerequisites (python3, node, yt-dlp, ffprobe) |
| 1 | Analyst | Fetches transcript via `yt-dlp --no-playlist` + `fetch_transcript.py` |
| 2 | Analyst | Extracts 15–20 key expressions → `expressions_grouped.json` |
| 3 | Director | Generates timed clip definitions → `clips.json` |
| 4 | QA | Validates clips (max 2 lines, 42 chars, 180s) and auto-fixes → `clips_fixed.json` |
| 5 | Director | Generates TypeScript data file → `src/data.ts` |
| 6 | Verify | Runs `npm run typecheck` to validate generated data |
| 7 | Preview | *(only with `--preview`)* Opens Remotion Studio in browser |
| 8 | Engineer | Renders all parts (LOW: sequential + 30s cooldown, HIGH: parallel) |
| 9 | Verify | Post-render checks (file size, resolution via ffprobe) |

The script stops immediately on any failure and reports which step broke.

### Performance Modes

Set `PERFORMANCE_MODE` in `.env`:

| Mode | When to Use | Rendering | Cooldown |
|------|------------|-----------|----------|
| **LOW** | Chromebook, <= 4GB RAM | Single-core, sequential | 30s between parts |
| **HIGH** | Desktop, 8GB+ RAM, CI | All cores, parallel | None |

### Supported YouTube URL Formats

All of these work — `--no-playlist` ensures only the single video is processed:

```
https://www.youtube.com/watch?v=XXXXX
https://www.youtube.com/watch?v=XXXXX&list=PLxxx&index=1
https://www.youtube.com/live/XXXXX?si=xxx
```

---

## Manual Step-by-Step

If you prefer to run each step individually (e.g., for debugging):

### Step 1: Fetch Transcript

```bash
# Download auto-generated captions from YouTube
yt-dlp --no-playlist --write-auto-sub --sub-lang en --skip-download \
  -o "data/%(title)s" "$YT_VIDEO_URL"

# Parse captions into clean JSON
python3 pipeline/fetch_transcript.py \
  --url "$YT_VIDEO_URL" \
  --out data/transcript.json
```

### Step 2: Extract Expressions

```bash
python3 pipeline/extract_expressions.py \
  --in data/transcript.json \
  --out data/expressions_grouped.json
```

### Step 3: Generate Clip Definitions

```bash
python3 pipeline/expressions_to_clips.py \
  --in data/expressions_grouped.json \
  --out data/clips.json
```

### Step 4: QA Validation

```bash
python3 pipeline/qa_validator.py \
  --in data/clips.json \
  --out data/qa_report.json
```

QA rules:

| Rule | Limit | Auto-Fix |
|---|---|---|
| Subtitle line count | Max 2 lines | Truncate to first 2 lines |
| Subtitle line length | Max 42 chars | Auto line-break at 42 characters |
| Clip duration | Max 180 seconds | Trim end to 180s from start |

Produces `data/clips_fixed.json` if fixes were needed.

### Step 5: Generate Remotion Data

```bash
python3 pipeline/generate_data_ts.py \
  --in data/clips_fixed.json \
  --out src/data.ts

# Verify TypeScript compiles
npm run typecheck
```

### Step 6: Preview (Optional)

```bash
npm run studio
```

Opens `http://localhost:3000` with timeline scrubbing, 9:16 preview, and per-part compositions.

| Key | Action |
|---|---|
| Space | Play / Pause |
| Left/Right Arrow | Step 1 frame |
| Shift + Left/Right | Step 10 frames |
| Home / End | Jump to start / end |

### Step 7: Render

```bash
# LOW profile (Chromebook)
npm run render:low -- part1 output/part1/shorts_final.mp4

# HIGH profile (Desktop)
npm run render:high -- part1 output/part1/shorts_final.mp4
```

### Step 8: Verify Output

```bash
ls -lh output/part1/shorts_final.mp4

ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,duration \
  -of csv=p=0 output/part1/shorts_final.mp4
# Expected: 1080,1920,<duration>
```

### Step 9: Generate SRT (Optional)

```bash
python3 pipeline/generate_srt.py \
  --in data/clips_fixed.json \
  --out output/part1/subtitles.srt
```

---

## FFmpeg Fallback (MVP Mode)

If Remotion fails or is unavailable:

```bash
# 1. Cut clips from source video
ffmpeg -ss 00:01:10 -i input.mp4 -t 12 -c copy clips/clip1.mp4

# 2. Add freeze frames for Korean overlays
ffmpeg -i clips/clip1.mp4 \
  -vf "tpad=stop_mode=clone:stop_duration=2" \
  -af "apad=pad_dur=2" \
  clips/clip1_freeze.mp4

# 3. Concatenate
echo "file 'clips/clip1_freeze.mp4'" > mylist.txt
echo "file 'clips/clip2.mp4'" >> mylist.txt
ffmpeg -f concat -safe 0 -i mylist.txt -c copy output/part1/shorts_final.mp4
```

---

## Troubleshooting

### Render fails with "font not found"
Edit `src/styles/theme.ts` to use system fallback fonts. The Engineer Agent auto-fixes this on retry.

### Render fails with "out of memory"
```bash
PERFORMANCE_MODE=LOW npm run render -- part1 output/part1/shorts_final.mp4 --concurrency=1
```

### TypeScript errors after generating data.ts
Re-run QA validation:
```bash
python3 pipeline/qa_validator.py --in data/clips.json --out data/qa_report.json
```

### Remotion Studio won't open
```bash
npx remotion browser ensure
```

### Self-Healing Loop
The Engineer Agent retries up to 3 times on render failure:
1. Parse `stderr` for known error patterns
2. Apply auto-fix (font patch, line-break fix, concurrency reduction)
3. Retry render
4. After 3 failures: halt and output `Render_Report.md`

---

## Output File Summary

```
output/
├── part1/
│   ├── shorts_final.mp4     # Final rendered YouTube Short (1080x1920, <= 180s)
│   ├── subtitles.srt         # Bilingual SRT for YouTube upload
│   ├── qa_report.json        # QA validation results
│   └── Render_Report.md      # Render metadata (time, size, resolution, warnings)
├── part2/
│   └── ...
data/
├── transcript.json            # Full cleaned transcript
├── expressions_grouped.json   # Linguistic analysis output
├── clips.json                 # Raw clip definitions
├── clips_fixed.json           # QA-corrected clip definitions
└── vector_cache.json          # Offline embedding cache
```
