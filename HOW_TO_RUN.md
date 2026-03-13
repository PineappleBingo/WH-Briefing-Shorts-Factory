# How to Run — Step-by-Step Guide

## Prerequisites

Before starting, ensure the following are installed on your machine:

| Tool | Version | Check Command | Purpose |
|---|---|---|---|
| Node.js | >= 18 | `node --version` | Remotion runtime |
| npm | >= 9 | `npm --version` | Package management |
| Python | >= 3.9 | `python3 --version` | Pipeline scripts |
| yt-dlp | latest | `yt-dlp --version` | Video/caption download |
| FFmpeg | >= 5.0 | `ffmpeg -version` | Fallback rendering, audio extraction |
| Chrome/Chromium | latest | — | Remotion uses headless Chrome for rendering |

---

## STEP 0: Clone & Install

```bash
# Clone the repository
git clone https://github.com/PineappleBingo/WH-Briefing-Shorts-Factory.git
cd WH-Briefing-Shorts-Factory

# Install Node.js dependencies
npm install

# Verify TypeScript compiles cleanly
npm run typecheck
```

---

## STEP 1: Configure Environment

```bash
# Copy the example env file
cp .env.example .env
```

Edit `.env` with your values:

```env
# Choose your hardware profile
# LOW  = Chromebook / low-spec (single-core, 30s cooldown between renders)
# HIGH = Desktop / CI (parallel rendering, all CPU cores)
PERFORMANCE_MODE=LOW

# Supabase (optional — for cross-briefing RAG search)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key

# Number of CPU cores for rendering (only used in HIGH mode)
REMOTION_CPU_CORES=4

# Target YouTube video URL
YT_VIDEO_URL=https://www.youtube.com/watch?v=XXXXX
```

**Which profile should I use?**
- **LOW**: You're on a Chromebook or machine with <= 4GB RAM. Renders one clip at a time with a 30-second pause between each to prevent overheating.
- **HIGH**: You're on a desktop, laptop with 8GB+ RAM, or CI server. Renders clips in parallel using all available CPU cores.

---

## STEP 2: Fetch Transcript (Analyst Agent — Phase 1)

Download the briefing video captions and convert them into a clean JSON transcript.

```bash
# Download auto-generated captions from YouTube
yt-dlp --no-playlist --write-auto-sub --sub-lang en --skip-download \
  -o "data/%(title)s" "$YT_VIDEO_URL"

# Run the transcript extraction pipeline
python3 pipeline/fetch_transcript.py \
  --url "$YT_VIDEO_URL" \
  --out data/transcript.json
```

**What this produces:**
- `data/transcript.json` — cleaned transcript with timestamps for every sentence

**Verify:**
```bash
# Check the transcript was created and has content
cat data/transcript.json | python3 -m json.tool | head -20
```

---

## STEP 3: Extract Expressions (Analyst Agent — Phase 2)

Analyze the transcript to extract 15–20 key English expressions suitable for B2–C1 Korean learners.

```bash
python3 pipeline/extract_expressions.py \
  --in data/transcript.json \
  --out data/expressions_grouped.json
```

**What this produces:**
- `data/expressions_grouped.json` — expressions grouped into sets of 5, each with:
  - Original sentence + timestamp
  - English definition
  - Korean explanation
  - Example sentence (EN/KR)

**Verify:**
```bash
# Should show groups of 5 expressions each
cat data/expressions_grouped.json | python3 -m json.tool | head -40
```

---

## STEP 4: Generate Clip Definitions (Director Agent — Phase 1)

Convert the grouped expressions into timed clip definitions with overlay text.

```bash
python3 pipeline/expressions_to_clips.py \
  --in data/expressions_grouped.json \
  --out data/clips.json
```

**What this produces:**
- `data/clips.json` — clip definitions with:
  - Start/end timestamps
  - Segment type (hook, expression, freeze_frame, wrapup)
  - Overlay text (EN + KR bilingual)
  - Highlight colors per keyword

**Verify:**
```bash
# Each part should have clips totaling <= 180 seconds
cat data/clips.json | python3 -m json.tool | head -50
```

---

## STEP 5: Run QA Validation (QA Module)

Validate all clips against production rules before rendering.

```bash
python3 pipeline/qa_validator.py \
  --in data/clips.json \
  --out data/qa_report.json
```

**Rules checked:**
| Rule | Limit | Auto-Fix |
|---|---|---|
| Subtitle line count | Max 2 lines | Truncate to first 2 lines |
| Subtitle line length | Max 42 chars | Auto line-break at 42 characters |
| Clip duration | Max 180 seconds | Trim end to 180s from start |

**What this produces:**
- `data/qa_report.json` — list of issues found and fixes applied
- `data/clips_fixed.json` — corrected clip definitions (if any issues were found)

**Verify:**
```bash
# Check if any issues were found
cat data/qa_report.json | python3 -m json.tool
```

---

## STEP 6: Generate Remotion Data (Director Agent — Phase 2)

Convert the validated clips into the TypeScript data file that Remotion consumes.

```bash
python3 pipeline/generate_data_ts.py \
  --in data/clips_fixed.json \
  --out src/data.ts
```

**What this produces:**
- `src/data.ts` — TypeScript file consumed by Remotion compositions, with strict timing sync between audio and captions

**Verify:**
```bash
# Type-check to make sure the generated data.ts is valid
npm run typecheck
```

---

## STEP 7: Preview in Remotion Studio (Optional but Recommended)

Open the visual preview to inspect compositions before rendering.

```bash
npm run studio
```

This opens a browser at `http://localhost:3000` where you can:
- See each Part as a separate composition in the left sidebar
- Scrub through the timeline frame by frame
- Verify caption placement, colors, and timing
- Check that the 9:16 aspect ratio looks correct on mobile preview

**Keyboard shortcuts in Studio:**
| Key | Action |
|---|---|
| Space | Play / Pause |
| Left/Right Arrow | Step 1 frame |
| Shift + Left/Right | Step 10 frames |
| Home / End | Jump to start / end |

---

## STEP 8: Render Final Videos (Engineer Agent)

### Option A: Remotion Render (Primary)

```bash
# LOW profile (Chromebook) — single-core, sequential
npm run render:low -- part1 output/part1/shorts_final.mp4

# HIGH profile (Desktop) — parallel, all cores
npm run render:high -- part1 output/part1/shorts_final.mp4
```

**Rendering multiple parts:**

```bash
# LOW profile — sequential with 30s cooldown
for part in part1 part2 part3; do
  npm run render:low -- $part output/$part/shorts_final.mp4
  echo "Cooling down for 30 seconds..."
  sleep 30
done

# HIGH profile — parallel (all at once)
for part in part1 part2 part3; do
  npm run render:high -- $part output/$part/shorts_final.mp4 &
done
wait
echo "All renders complete."
```

### Option B: FFmpeg Fallback (MVP Mode)

If Remotion fails or is unavailable, use the FFmpeg pipeline:

```bash
# 1. Cut individual clips from the source video
ffmpeg -ss 00:01:10 -i input.mp4 -t 12 -c copy clips/clip1.mp4
ffmpeg -ss 00:03:45 -i input.mp4 -t 10 -c copy clips/clip2.mp4
# ... repeat for each clip

# 2. Add freeze frames for Korean explanation overlays
ffmpeg -i clips/clip1.mp4 \
  -vf "tpad=stop_mode=clone:stop_duration=2" \
  -af "apad=pad_dur=2" \
  clips/clip1_freeze.mp4

# 3. Create concat list
echo "file 'clips/clip1_freeze.mp4'" > mylist.txt
echo "file 'clips/clip2.mp4'" >> mylist.txt

# 4. Concatenate into final Short
ffmpeg -f concat -safe 0 -i mylist.txt -c copy output/part1/shorts_final.mp4
```

---

## STEP 9: Post-Render Verification

After rendering, verify the output:

```bash
# Check file exists and has reasonable size (should be > 1MB for a 60s+ video)
ls -lh output/part1/shorts_final.mp4

# Verify resolution is 1080x1920 (9:16 vertical)
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,duration \
  -of csv=p=0 output/part1/shorts_final.mp4

# Expected output: 1080,1920,<duration_in_seconds>
```

---

## STEP 10: Generate SRT Subtitles (Optional)

Create an SRT subtitle file for YouTube accessibility:

```bash
python3 pipeline/generate_srt.py \
  --in data/clips_fixed.json \
  --out output/part1/subtitles.srt
```

Upload `subtitles.srt` alongside the video on YouTube for bilingual captions.

---

## Quick Reference — Full Pipeline in One Go

```bash
# === CONFIGURE ===
cp .env.example .env
# Edit .env with your YT_VIDEO_URL and PERFORMANCE_MODE

# === PIPELINE ===
python3 pipeline/fetch_transcript.py     --url "$YT_VIDEO_URL" --out data/transcript.json
python3 pipeline/extract_expressions.py  --in data/transcript.json --out data/expressions_grouped.json
python3 pipeline/expressions_to_clips.py --in data/expressions_grouped.json --out data/clips.json
python3 pipeline/qa_validator.py         --in data/clips.json --out data/qa_report.json
python3 pipeline/generate_data_ts.py     --in data/clips_fixed.json --out src/data.ts

# === VERIFY ===
npm run typecheck

# === PREVIEW (optional) ===
npm run studio

# === RENDER ===
npm run render:low -- part1 output/part1/shorts_final.mp4
```

---

## Troubleshooting

### Render fails with "font not found"
The Engineer Agent auto-fixes this by patching `src/styles/theme.ts` to use system fallback fonts. You can also manually edit the `fonts` section in `src/styles/theme.ts`.

### Render fails with "out of memory"
Switch to LOW profile or reduce concurrency:
```bash
PERFORMANCE_MODE=LOW npm run render -- part1 output/part1/shorts_final.mp4 --concurrency=1
```

### TypeScript errors after generating data.ts
Run the QA validator to ensure clip data conforms to the expected schema:
```bash
python3 pipeline/qa_validator.py --in data/clips.json --out data/qa_report.json
```

### Remotion Studio won't open
Ensure Chrome/Chromium is installed. On headless Linux:
```bash
npx remotion browser ensure
```

### Self-Healing Loop
The Engineer Agent automatically retries up to 3 times on render failure:
1. Parse `stderr` for known error patterns
2. Apply auto-fix (font patch, line-break fix, concurrency reduction)
3. Retry render
4. After 3 failures: halt and output detailed `Render_Report.md`

---

## Output File Summary

After a successful run, you'll have:

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
