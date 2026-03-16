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

### Fix 1: New `pipeline/enrich_expressions.py` script

A new pipeline step between extraction and clip generation that calls the Claude API to:
- Generate real `definition_en`, `explanation_kr`, `example_en`, `example_kr` for each expression
- Judge whether single-word catalog matches are worth keeping (`keep: true/false`)
- Remove rejected expressions from groups before clip generation

**Input:** `data/expressions_grouped.json`
**Output:** `data/expressions_enriched.json` (same schema, real definitions, filtered)

**API call structure:** One call per group of 5 expressions (not one call per expression) to minimize latency and cost.

**Model selection** (respects `PERFORMANCE_MODE`):
- `LOW` → `claude-haiku-4-5-20251001`
- `HIGH` → `claude-sonnet-4-6`

**Rejection logic:** Multi-word expressions always pass. Single-word items are evaluated by Claude based on pedagogical value in context. Rejected expressions are removed from the group. Groups that fall below 3 expressions after filtering emit a warning but are not discarded.

**New env var required:** `ANTHROPIC_API_KEY` — validated at pipeline startup.

---

### Fix 2: `qa_validator.py` minimum source clip duration guard

New validation rule `min_source_duration`:

- Checks `clipEndSec - clipStartSec < 2.0` on any clip with source video fields
- Discards the clip and logs a QA issue
- Drops all 3 passes (`expression_raw`, `expression_blank`, `expression_reveal`) for the affected expression since they share the same source segment
- Logged as `auto_fixed: true` in `qa_report.json`

Threshold: **2.0 seconds** minimum source clip duration.

---

### Fix 3: `run_pipeline.sh` pipeline integration

Insert Step 2.5 between extraction and clip generation:

```
Step 2:   extract_expressions.py    → data/expressions_grouped.json
Step 2.5: enrich_expressions.py     → data/expressions_enriched.json  ← NEW
Step 3:   expressions_to_clips.py   → data/clips.json  (reads enriched)
```

`expressions_to_clips.py` input changed from `expressions_grouped.json` to `expressions_enriched.json`.

`.env.example` updated with `ANTHROPIC_API_KEY`.

Step 0 prerequisite check validates `ANTHROPIC_API_KEY` is set before proceeding.

---

## File Changes

| File | Change |
|---|---|
| `pipeline/enrich_expressions.py` | **New file** |
| `pipeline/qa_validator.py` | Add `min_source_duration` rule |
| `run_pipeline.sh` | Add Step 2.5, update Step 3 input, validate API key |
| `.env.example` | Add `ANTHROPIC_API_KEY` |

## Data Flow

```
data/transcript.json
  └─ extract_expressions.py
       └─ data/expressions_grouped.json   (raw, placeholders)
            └─ enrich_expressions.py (Claude API)
                 └─ data/expressions_enriched.json  (real definitions, filtered)
                      └─ expressions_to_clips.py
                           └─ data/clips.json
                                └─ qa_validator.py  (+ min_source_duration guard)
                                     └─ data/clips_fixed.json
                                          └─ generate_data_ts.py
                                               └─ src/data.ts
```

## Out of Scope

- Rewriting `fetch_transcript.py` to fix VTT triple-duplication in `original_sentence`
- Removing single-word items from `EXPRESSION_CATALOG` (Claude filters at enrichment time instead)
- Changing the 3-pass Remotion composition logic
