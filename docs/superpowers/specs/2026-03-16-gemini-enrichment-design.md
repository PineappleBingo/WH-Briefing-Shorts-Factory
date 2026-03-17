# Design: Replace Anthropic with Gemini Fallback Chain for Expression Enrichment

**Date:** 2026-03-16
**Status:** Approved

## Problem Summary

`pipeline/enrich_expressions.py` currently uses the Anthropic Claude API to enrich expressions. The user wants to replace this with Google Gemini, using a free-to-paid fallback chain that automatically advances to a more capable model on any failure or quality issue.

`gemini-2.0-flash` and `gemini-2.0-flash-lite` are deprecated (retiring March–June 2026) and must not be used.

---

## Solution Overview

### New file: `pipeline/gemini_client.py`

Single public function: `call_gemini(prompt: str, api_key: str) -> str`

**Fallback chain (in order):**

| # | Model ID | Tier | Notes |
|---|---|---|---|
| 1 | `gemini-2.5-flash-lite` | Free (15 RPM, 1000 RPD) | Fastest, cheapest |
| 2 | `gemini-2.5-flash` | Free (10 RPM) | Better quality |
| 3 | `gemini-2.5-pro` | Free (5 RPM) | Best quality |

**Advance to next model on:**
- Any API or network error (`google.api_core.exceptions.GoogleAPIError`, connection errors)
- Rate limit / quota exceeded (`ResourceExhausted`, HTTP 429)
- Response is unparseable JSON (quality failure)
- Response JSON is missing any required field (`definition_en`, `explanation_kr`, `example_en`, `example_kr`, `keep`)

**When all 3 models fail:** raise `RuntimeError` with the last error/reason. `main()` catches this and exits with code 1.

**SDK:** `google-generativeai` Python package.

---

### Modified: `pipeline/enrich_expressions.py`

Three changes only — pure functions (`filter_short_clips`, `build_prompt`, `parse_enrichment_response`) are untouched:

1. Remove `import anthropic` and all Anthropic SDK references
2. Replace `client.messages.create(...)` call in `enrich_group` with `call_gemini(prompt, api_key)` — single line swap
3. Update `main()`:
   - Read `GEMINI_API_KEY` instead of `ANTHROPIC_API_KEY`
   - Remove model selection logic (no more `PERFORMANCE_MODE` → model mapping — `gemini_client.py` owns the chain)
   - Exception handler catches `RuntimeError` from `call_gemini` instead of `anthropic.APIError`/`APIConnectionError`

---

### Modified: `tests/test_enrich_expressions.py`

- Replace `mock_client.messages.create` mocks with `mocker.patch("pipeline.enrich_expressions.call_gemini", ...)`
- Update `TestMain` to patch `GEMINI_API_KEY` instead of `ANTHROPIC_API_KEY`
- Remove `test_api_error_propagates` and `test_connection_error_propagates` from `TestEnrichGroup` — these move to `test_gemini_client.py`

---

### New: `tests/test_gemini_client.py`

Tests for `call_gemini`:

| Test | What it verifies |
|---|---|
| `test_succeeds_on_first_model` | Returns response text when first model works |
| `test_falls_back_on_api_error` | Advances to next model on `GoogleAPIError` |
| `test_falls_back_on_rate_limit` | Advances to next model on `ResourceExhausted` |
| `test_falls_back_on_malformed_json` | Advances to next model when response is not valid JSON |
| `test_falls_back_on_missing_fields` | Advances to next model when required fields absent |
| `test_raises_when_all_models_fail` | Raises `RuntimeError` after all 3 models fail |

---

### Modified: `run_pipeline.sh`

One change: `ANTHROPIC_API_KEY` → `GEMINI_API_KEY` in the hard-fail env var check and error message.

---

### Modified: `Pipfile`

- Add `google-generativeai = "*"` to `[packages]`
- Remove `anthropic` from `[packages]` (no longer used anywhere)

---

### Modified: `.env.example`

- Replace `ANTHROPIC_API_KEY=...` with `GEMINI_API_KEY=your_gemini_api_key_here`

---

## File Changes

| File | Change |
|---|---|
| `pipeline/gemini_client.py` | **New** — `call_gemini` with 3-model fallback chain |
| `pipeline/enrich_expressions.py` | Remove anthropic, use `call_gemini`, use `GEMINI_API_KEY` |
| `tests/test_gemini_client.py` | **New** — 6 tests for `call_gemini` |
| `tests/test_enrich_expressions.py` | Update mocks to patch `call_gemini`, update env var refs |
| `run_pipeline.sh` | `ANTHROPIC_API_KEY` → `GEMINI_API_KEY` |
| `Pipfile` | Add `google-generativeai`, remove `anthropic` |
| `.env.example` | `ANTHROPIC_API_KEY` → `GEMINI_API_KEY` |

---

## Out of Scope

- Adding Gemini 3.x paid-only models to the chain
- Keeping Anthropic as a final fallback
- Changing the prompt format or enrichment schema
- Changing `PERFORMANCE_MODE` behavior (model selection is now internal to `gemini_client.py`)
