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

**Return value:** The raw response body text string from the first successful model. Always a plain `str` — never a parsed object or SDK response type.

**Fallback chain (in order):**

| # | Model ID | Tier | Notes |
|---|---|---|---|
| 1 | `gemini-2.5-flash-lite` | Free (15 RPM, 1000 RPD) | Fastest, cheapest |
| 2 | `gemini-2.5-flash` | Free (10 RPM) | Better quality |
| 3 | `gemini-2.5-pro` | Free (5 RPM) | Best quality |

**Advance to next model on (4 triggers):**
1. Any API or network error (`google.api_core.exceptions.GoogleAPIError`, connection errors)
2. Rate limit / quota exceeded (`ResourceExhausted`, HTTP 429)
3. Response body is not parseable as JSON
4. Response JSON parses successfully but **any single object** in the array is missing one or more required fields (`definition_en`, `explanation_kr`, `example_en`, `example_kr`, `keep`) — the entire call is retried with the next model; partial arrays are not accepted

**Quality validation is internal to `call_gemini`:** The function parses the JSON response internally to check required field presence. If validation passes, it returns the raw text string to the caller. The caller (`parse_enrichment_response`) re-parses the same string — this is intentional. `call_gemini` is responsible only for ensuring a structurally valid response was received; `parse_enrichment_response` handles semantic filtering (`keep: false`).

**All-`keep: false` responses are acceptable:** If a model returns valid JSON with all required fields present, but sets `keep: false` on every expression, `call_gemini` considers this a successful response and returns it. It is not a quality failure. The group will end up empty after `parse_enrichment_response` filters, and the existing warning path in `enrich_group` handles that. A smarter model is not retried solely because all expressions were rejected.

**When all 3 models fail:** raise `RuntimeError` with a message in the format: `"All 3 Gemini models failed. Last failure (<model-id>): <reason>"`. `main()` catches this and exits with code 1.

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
