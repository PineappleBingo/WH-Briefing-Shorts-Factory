#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# WH Briefing Shorts Factory — Full Pipeline Runner
# Usage: ./run_pipeline.sh [--skip-render] [--skip-preview]
# ============================================================

# --- Parse flags ---
SKIP_RENDER=false
SKIP_PREVIEW=true  # preview requires interactive browser, skip by default
for arg in "$@"; do
  case "$arg" in
    --skip-render)  SKIP_RENDER=true ;;
    --preview)      SKIP_PREVIEW=false ;;
    --help|-h)
      echo "Usage: ./run_pipeline.sh [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --skip-render   Run pipeline up to data generation, skip video rendering"
      echo "  --preview       Open Remotion Studio for visual preview before rendering"
      echo "  -h, --help      Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg (use --help for usage)"
      exit 1
      ;;
  esac
done

# --- Load .env ---
if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Run: cp .env.example .env  and fill in your values."
  exit 1
fi
set -a
source .env
set +a

# --- Validate required env vars ---
if [ -z "${YT_VIDEO_URL:-}" ]; then
  echo "ERROR: YT_VIDEO_URL is not set in .env"
  exit 1
fi
if [ -z "${PERFORMANCE_MODE:-}" ]; then
  echo "WARNING: PERFORMANCE_MODE not set, defaulting to LOW"
  PERFORMANCE_MODE=LOW
fi

# --- Colors for output ---
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

step() {
  echo ""
  echo -e "${CYAN}========================================${NC}"
  echo -e "${CYAN}  STEP $1: $2${NC}"
  echo -e "${CYAN}========================================${NC}"
}

success() {
  echo -e "${GREEN}  [OK] $1${NC}"
}

fail() {
  echo -e "${RED}  [FAIL] $1${NC}"
  exit 1
}

warn() {
  echo -e "${YELLOW}  [WARN] $1${NC}"
}

# --- Prerequisite checks ---
step "0" "Checking prerequisites"

command -v python3 >/dev/null 2>&1 || fail "python3 is not installed"
success "python3 found"

command -v node >/dev/null 2>&1 || fail "node is not installed"
success "node $(node --version) found"

command -v yt-dlp >/dev/null 2>&1 || fail "yt-dlp is not installed (pip install yt-dlp)"
success "yt-dlp found"

if command -v ffprobe >/dev/null 2>&1; then
  success "ffprobe found (post-render verification enabled)"
  HAS_FFPROBE=true
else
  warn "ffprobe not found — post-render verification will be skipped"
  HAS_FFPROBE=false
fi

[ -d node_modules ] || { echo "  Installing npm dependencies..."; npm install; }
success "node_modules ready"

# --- Ensure output directories exist ---
mkdir -p data output

echo ""
echo -e "  Video URL:        ${YT_VIDEO_URL}"
echo -e "  Performance Mode: ${PERFORMANCE_MODE}"
echo ""

# ============================================================
# PHASE 1: ANALYST — Fetch & Analyze
# ============================================================

step "1" "Fetching transcript (yt-dlp + fetch_transcript.py)"

yt-dlp --no-playlist --write-auto-sub --sub-lang en --skip-download \
  -o "data/%(title)s" "$YT_VIDEO_URL"

python3 pipeline/fetch_transcript.py \
  --url "$YT_VIDEO_URL" \
  --out data/transcript.json

[ -f data/transcript.json ] || fail "data/transcript.json was not created"
success "data/transcript.json created"

step "2" "Extracting expressions (extract_expressions.py)"

python3 pipeline/extract_expressions.py \
  --in data/transcript.json \
  --out data/expressions_grouped.json

[ -f data/expressions_grouped.json ] || fail "data/expressions_grouped.json was not created"
success "data/expressions_grouped.json created"

# ============================================================
# PHASE 2: DIRECTOR — Clip Definitions & Data Generation
# ============================================================

step "3" "Generating clip definitions (expressions_to_clips.py)"

python3 pipeline/expressions_to_clips.py \
  --in data/expressions_grouped.json \
  --out data/clips.json

[ -f data/clips.json ] || fail "data/clips.json was not created"
success "data/clips.json created"

step "4" "Running QA validation (qa_validator.py)"

python3 pipeline/qa_validator.py \
  --in data/clips.json \
  --out data/qa_report.json

# QA produces clips_fixed.json if fixes were needed, otherwise use clips.json
if [ -f data/clips_fixed.json ]; then
  success "QA applied fixes → data/clips_fixed.json"
  CLIPS_INPUT=data/clips_fixed.json
else
  success "QA passed with no fixes needed"
  CLIPS_INPUT=data/clips.json
fi

step "5" "Generating Remotion data (generate_data_ts.py)"

python3 pipeline/generate_data_ts.py \
  --in "$CLIPS_INPUT" \
  --out src/data.ts

[ -f src/data.ts ] || fail "src/data.ts was not created"
success "src/data.ts created"

step "6" "TypeScript validation"

npm run typecheck || fail "TypeScript type-check failed — check src/data.ts"
success "TypeScript compiles cleanly"

# ============================================================
# PHASE 3: ENGINEER — Preview & Render
# ============================================================

if [ "$SKIP_PREVIEW" = false ]; then
  step "7" "Opening Remotion Studio (preview)"
  echo "  Close the browser tab or press Ctrl+C when done previewing."
  npm run studio
fi

if [ "$SKIP_RENDER" = true ]; then
  echo ""
  echo -e "${GREEN}Pipeline complete (rendering skipped).${NC}"
  echo "  To render manually:  npm run render:low -- part1 output/part1/shorts_final.mp4"
  exit 0
fi

step "8" "Rendering final videos"

# Discover all part IDs from clips JSON (used to generate data.ts)
CLIPS_SOURCE="$CLIPS_INPUT"
if [ ! -f "$CLIPS_SOURCE" ]; then
  CLIPS_SOURCE=data/clips.json
fi
PARTS=$(python3 -c "
import json, sys
with open('$CLIPS_SOURCE') as f:
    d = json.load(f)
for p in d['parts']:
    print(p['id'])
" 2>/dev/null || echo "part1")

RENDER_CMD="render:low"
COOLDOWN=30
if [ "$PERFORMANCE_MODE" = "HIGH" ]; then
  RENDER_CMD="render:high"
  COOLDOWN=0
fi

PART_COUNT=0
for part in $PARTS; do
  PART_COUNT=$((PART_COUNT + 1))
  mkdir -p "output/$part"
  echo ""
  echo -e "  Rendering ${CYAN}${part}${NC} (${PERFORMANCE_MODE} profile)..."

  npm run "$RENDER_CMD" -- "$part" "output/$part/shorts_final.mp4" \
    || fail "Render failed for $part"

  success "$part rendered → output/$part/shorts_final.mp4"

  # Cooldown between renders in LOW mode (skip after last part)
  if [ "$COOLDOWN" -gt 0 ] && [ "$PART_COUNT" -lt "$(echo "$PARTS" | wc -w)" ]; then
    echo -e "  ${YELLOW}Cooling down ${COOLDOWN}s...${NC}"
    sleep "$COOLDOWN"
  fi
done

# ============================================================
# PHASE 4: POST-RENDER VERIFICATION
# ============================================================

step "9" "Post-render verification"

ALL_OK=true
for part in $PARTS; do
  OUTPUT="output/$part/shorts_final.mp4"
  if [ ! -f "$OUTPUT" ]; then
    echo -e "  ${RED}[MISSING] $OUTPUT${NC}"
    ALL_OK=false
    continue
  fi

  SIZE=$(stat --format="%s" "$OUTPUT" 2>/dev/null || stat -f "%z" "$OUTPUT" 2>/dev/null || echo "0")
  SIZE_MB=$(python3 -c "print(f'{$SIZE/1048576:.1f}')" 2>/dev/null || echo "?")
  echo -e "  $part: ${SIZE_MB} MB"

  if [ "$HAS_FFPROBE" = true ]; then
    INFO=$(ffprobe -v error -select_streams v:0 \
      -show_entries stream=width,height,duration \
      -of csv=p=0 "$OUTPUT" 2>/dev/null || echo "error")
    echo -e "    Resolution/Duration: $INFO"
  fi
done

# ============================================================
# DONE
# ============================================================

echo ""
if [ "$ALL_OK" = true ]; then
  echo -e "${GREEN}============================================${NC}"
  echo -e "${GREEN}  Pipeline complete! All parts rendered.${NC}"
  echo -e "${GREEN}============================================${NC}"
else
  echo -e "${RED}============================================${NC}"
  echo -e "${RED}  Pipeline finished with errors. Check above.${NC}"
  echo -e "${RED}============================================${NC}"
  exit 1
fi

echo ""
echo "Output files:"
for part in $PARTS; do
  echo "  output/$part/shorts_final.mp4"
done
echo ""
echo "Optional next steps:"
echo "  - Generate SRT:  python3 pipeline/generate_srt.py --in $CLIPS_INPUT --out output/part1/subtitles.srt"
echo "  - Preview again: npm run studio"
