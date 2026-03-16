# Design: Expression Enrichment Pipeline Fix

**Date:** 2026-03-15
**Status:** Approved

## Problem Summary

Three bugs were identified in the expression extraction pipeline:

1. **Placeholder definitions** — `extract_expressions.py` always writes `[Definition of 'X']` template strings. The Analyst Agent step that was supposed to fill these in is never called by `run_pipeline.sh`.
2. **Single-word vocabulary dominates** — The `EXPRESSION_CATALOG` contains ~40 single-word political terms that win by frequency over multi-word idioms. Output contains REITERATE, FILIBUSTER, COALITION instead of true expressions.
3. **Zero-length source clips** — FILIBUSTER (`0.01s`) and COALITION (`0.01s`) matched on VTT cues with near-identical start/end timestamps. The 3-pass render system tries to replay these across 14 seconds of animation.

---

## Solution Overview

### Fix 1 + 3: New `pipeline/enrich_expressions.py` script

A new pipeline step between extraction and clip generation that calls the Claude API to:
- Generate real `definition_en`, `explanation_kr`, `example_en`, `example_kr` for each expression
- Judge whether single-word catalog matches are worth keeping (`keep: true/false`)
- **Discard expressions with source clip duration < 2.0s** (fixes Fix 3 before clip expansion)
- Remove rejected expressions from groups before clip generation

This script is also the correct location for the duration guard (Fix 3). Moving it here means `expressions_to_clips.py` never sees bad-duration expressions, avoiding the need to correlate expanded 3-pass clips in the QA validator.

**Input:** `data/expressions_grouped.json`
**Output:** `data/expressions_enriched.json` (see schema below)

**API call structure:** One call per group of 5 expressions (not one call per expression) to minimize latency and cost.

**Model selection** (respects `PERFORMANCE_MODE`):
- `LOW` → `claude-haiku-4-5-20251001`
- `HIGH` → `claude-sonnet-4-6`

**Rejection logic:**
- Multi-word expressions always pass the `keep` check.
- Single-word items are evaluated by Claude based on pedagogical value in context.
- Expressions with `end - start < 2.0` are discarded regardless of Claude's judgment.
- Rejected/discarded expressions are removed from the group.
- Groups that fall below 3 expressions after filtering emit a warning but are not discarded.
- `total_expressions` at the root of the output file is recomputed post-filter.

**Error handling:**
- On Claude API failure (network error, 5xx, rate limit, malformed JSON response): exit non-zero with a clear error message. Do not write a partial output file.

**`expressions_enriched.json` schema** — same root structure as `expressions_grouped.json` with these changes per expression:

```json
{
  "expression": "REST ASSURED",
  "original_sentence": "...",
  "start": 185.28,   // video-level timestamp (seconds into source video) where expression appears
  "end": 324.71,     // end of the VTT cue window containing the expression (not expression duration)
  "definition_en": "Used to tell someone they should not worry about something.",
  "explanation_kr": "'rest assured'는 '안심하세요'라는 뜻으로, 상대방을 안심시킬 때 씁니다.",
  "example_en": "Rest assured, your data is safe with us.",
  "example_kr": "안심하세요, 여러분의 데이터는 안전합니다.",
  "cefr_level": "C1",
  "highlight_color": "#FFD700"
}
```

Note: The `keep` field is consumed internally and **not written** to the output file. The output schema is otherwise identical to `expressions_grouped.json`.

---

### Fix 2: `qa_validator.py` minimum source clip duration guard (backstop only)

The primary duration guard lives in `enrich_expressions.py`. The QA validator adds a hard backstop rule `min_source_duration` as a second line of defense:

- Checks `clipEndSec - clipStartSec < 1.0` on any clip with source video fields (stricter threshold than the enrichment filter's 2.0s — catches anything that slips through)
- Discards the clip and logs a QA issue
- Because bad expressions are already filtered in enrichment, this rule should never trigger in normal operation — it is a safety net only
- Logged as `auto_fixed: true` in `qa_report.json`

```json
{
  "rule": "min_source_duration",
  "detail": "source clip 0.01s (min 1.0s) — clip dropped",
  "auto_fixed": true
}
```

---

### Fix 4: `run_pipeline.sh` pipeline integration

Insert Step 2.5 between extraction and clip generation:

```
Step 2:   extract_expressions.py    → data/expressions_grouped.json
Step 2.5: enrich_expressions.py     → data/expressions_enriched.json  ← NEW
Step 3:   expressions_to_clips.py   → data/clips.json  (reads enriched)
```

`expressions_to_clips.py` input changed from `expressions_grouped.json` to `expressions_enriched.json`.

**`ANTHROPIC_API_KEY` is a hard fail** — missing key calls `fail` (exits 1) in Step 0, not a warning. Validated before any other steps run.

`.env.example` updated with `ANTHROPIC_API_KEY`.

---

## File Changes

| File | Change |
|---|---|
| `pipeline/enrich_expressions.py` | **New file** — Claude API enrichment + duration guard |
| `pipeline/qa_validator.py` | Add `min_source_duration` backstop rule (threshold 1.0s) |
| `run_pipeline.sh` | Add Step 2.5, update Step 3 input, hard-fail on missing API key |
| `.env.example` | Add `ANTHROPIC_API_KEY` |

`expressions_to_clips.py` requires **no changes** — it reads whatever JSON is passed via `--in`.

---

## Data Flow

```
data/transcript.json
  └─ extract_expressions.py
       └─ data/expressions_grouped.json   (raw, placeholders)
            └─ enrich_expressions.py (Claude API, duration filter)
                 └─ data/expressions_enriched.json  (real definitions, filtered)
                      └─ expressions_to_clips.py
                           └─ data/clips.json
                                └─ qa_validator.py  (+ min_source_duration backstop)
                                     └─ data/clips_fixed.json  (only if QA finds issues)
                                          └─ generate_data_ts.py  (reads clips_fixed.json
                                                                    or clips.json if no fixes)
                                               └─ src/data.ts
```

---

## Out of Scope

- Rewriting `fetch_transcript.py` to fix VTT triple-duplication in `original_sentence`
- Removing single-word items from `EXPRESSION_CATALOG` (Claude filters at enrichment time instead)
- Changing the 3-pass Remotion composition logic
