# Expression Enrichment Pipeline Fix — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Claude API enrichment step to the pipeline that replaces placeholder definitions, filters out weak single-word picks, and discards zero-length source clips before they reach the Remotion renderer.

**Architecture:** A new `pipeline/enrich_expressions.py` script runs between extraction and clip generation. It calls the Claude API once per expression group (5 expressions = 1 API call), applies a source clip duration filter, and writes `data/expressions_enriched.json`. A backstop duration guard is also added to `qa_validator.py`. `run_pipeline.sh` wires in the new step and hard-fails on a missing `ANTHROPIC_API_KEY`.

**Tech Stack:** Python 3.10, `anthropic` SDK (already in Pipfile), `pytest` + `pytest-mock` (added as dev deps), bash.

**Spec:** `docs/superpowers/specs/2026-03-15-enrich-expressions-design.md`

---

## Chunk 1: `pipeline/enrich_expressions.py`

### Task 1: Add pytest dev dependencies

**Files:**
- Modify: `Pipfile`

- [ ] **Step 1: Add pytest and pytest-mock to Pipfile dev-packages**

Edit `Pipfile` so `[dev-packages]` reads:

```toml
[dev-packages]
pytest = "*"
pytest-mock = "*"
```

- [ ] **Step 2: Install dev dependencies**

```bash
pipenv install --dev
```

Expected: `pytest` and `pytest-mock` installed into the pipenv virtualenv.

- [ ] **Step 3: Verify pytest runs**

```bash
pipenv run pytest --version
```

Expected output contains: `pytest 8.x.x`

- [ ] **Step 4: Commit**

```bash
git add Pipfile Pipfile.lock
git commit -m "chore: add pytest and pytest-mock as dev dependencies"
```

---

### Task 2: Write failing tests for `filter_short_clips`, `build_prompt`, `parse_enrichment_response`

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_enrich_expressions.py`

- [ ] **Step 1: Create empty `tests/__init__.py`**

Create `tests/__init__.py` with empty contents.

- [ ] **Step 2: Write failing tests**

Create `tests/test_enrich_expressions.py`:

```python
"""Tests for pipeline/enrich_expressions.py"""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from pipeline.enrich_expressions import (
    filter_short_clips,
    build_prompt,
    parse_enrichment_response,
)


def make_expr(expression, start, end):
    return {
        "expression": expression,
        "original_sentence": f"Sample sentence with {expression.lower()}.",
        "start": start,
        "end": end,
        "definition_en": "[placeholder]",
        "explanation_kr": "[placeholder]",
        "example_en": "[placeholder]",
        "example_kr": "[placeholder]",
        "cefr_level": "B2",
        "highlight_color": "#00BFFF",
    }


class TestFilterShortClips:
    def test_keeps_long_enough_clips(self):
        expressions = [make_expr("ON THE TABLE", 100.0, 110.0)]
        valid, discarded = filter_short_clips(expressions)
        assert len(valid) == 1
        assert len(discarded) == 0

    def test_discards_zero_length_clip(self):
        expressions = [make_expr("FILIBUSTER", 1196.789, 1196.799)]
        valid, discarded = filter_short_clips(expressions)
        assert len(valid) == 0
        assert len(discarded) == 1
        assert discarded[0]["expression"] == "FILIBUSTER"

    def test_discards_clip_at_threshold(self):
        # duration == 2.0 is discarded — filter requires duration > min_duration (strictly greater than)
        expressions = [make_expr("REITERATE", 100.0, 102.0)]
        valid, discarded = filter_short_clips(expressions)
        assert len(valid) == 0
        assert len(discarded) == 1

    def test_keeps_clip_just_above_threshold(self):
        # duration == 2.001 passes because 2.001 > 2.0
        expressions = [make_expr("REST ASSURED", 100.0, 102.001)]
        valid, discarded = filter_short_clips(expressions)
        assert len(valid) == 1
        assert len(discarded) == 0

    def test_mixed_clips(self):
        expressions = [
            make_expr("ON THE TABLE", 100.0, 115.0),   # valid
            make_expr("FILIBUSTER", 200.0, 200.01),    # too short
            make_expr("GOOD FAITH", 300.0, 320.0),     # valid
        ]
        valid, discarded = filter_short_clips(expressions)
        assert len(valid) == 2
        assert len(discarded) == 1
        assert valid[0]["expression"] == "ON THE TABLE"
        assert valid[1]["expression"] == "GOOD FAITH"
        assert discarded[0]["expression"] == "FILIBUSTER"

    def test_custom_min_duration(self):
        expressions = [make_expr("VETO", 100.0, 104.0)]
        valid, discarded = filter_short_clips(expressions, min_duration=5.0)
        assert len(valid) == 0
        assert len(discarded) == 1


class TestBuildPrompt:
    def test_prompt_contains_all_expressions(self):
        expressions = [
            make_expr("ON THE TABLE", 100.0, 115.0),
            make_expr("GOOD FAITH", 300.0, 320.0),
        ]
        prompt = build_prompt(expressions)
        assert "ON THE TABLE" in prompt
        assert "GOOD FAITH" in prompt

    def test_prompt_requests_json_array(self):
        expressions = [make_expr("VETO", 100.0, 110.0)]
        prompt = build_prompt(expressions)
        assert "JSON" in prompt or "json" in prompt

    def test_prompt_includes_context_sentence(self):
        expr = make_expr("VETO", 100.0, 110.0)
        expr["original_sentence"] = "The president used his veto power."
        prompt = build_prompt([expr])
        assert "veto power" in prompt


class TestParseEnrichmentResponse:
    def make_api_response(self, items):
        return json.dumps(items)

    def test_replaces_placeholders_with_real_definitions(self):
        original = [make_expr("ON THE TABLE", 100.0, 115.0)]
        response = self.make_api_response([{
            "expression": "ON THE TABLE",
            "definition_en": "Available for consideration or negotiation.",
            "explanation_kr": "'on the table'은 협상 테이블에 올라와 있다는 뜻입니다.",
            "example_en": "All options are on the table.",
            "example_kr": "모든 선택지가 논의 대상입니다.",
            "keep": True,
        }])
        result = parse_enrichment_response(response, original)
        assert len(result) == 1
        assert result[0]["definition_en"] == "Available for consideration or negotiation."
        assert "[placeholder]" not in result[0]["explanation_kr"]

    def test_filters_out_keep_false_expressions(self):
        original = [
            make_expr("ON THE TABLE", 100.0, 115.0),
            make_expr("COALITION", 200.0, 215.0),
        ]
        response = self.make_api_response([
            {
                "expression": "ON THE TABLE",
                "definition_en": "Available for consideration.",
                "explanation_kr": "협상에 올라온 상태.",
                "example_en": "All options are on the table.",
                "example_kr": "모든 선택지가 논의 대상입니다.",
                "keep": True,
            },
            {
                "expression": "COALITION",
                "definition_en": "A group formed by multiple parties.",
                "explanation_kr": "연합.",
                "example_en": "They formed a coalition.",
                "example_kr": "그들은 연합을 형성했습니다.",
                "keep": False,
                "rejection_reason": "Basic vocabulary, not a teaching-worthy expression",
            },
        ])
        result = parse_enrichment_response(response, original)
        assert len(result) == 1
        assert result[0]["expression"] == "ON THE TABLE"

    def test_strips_markdown_code_fences(self):
        original = [make_expr("VETO", 100.0, 110.0)]
        raw = (
            '```json\n'
            '[{"expression":"VETO","definition_en":"A rejection.","explanation_kr":"거부권.",'
            '"example_en":"He used his veto.","example_kr":"그는 거부권을 행사했습니다.","keep":true}]\n'
            '```'
        )
        result = parse_enrichment_response(raw, original)
        assert len(result) == 1
        assert result[0]["definition_en"] == "A rejection."

    def test_raises_on_malformed_json(self):
        original = [make_expr("VETO", 100.0, 110.0)]
        with pytest.raises(ValueError, match="Failed to parse"):
            parse_enrichment_response("not json at all", original)

    def test_zip_truncates_gracefully_on_short_response(self):
        # If Claude returns fewer items than expressions, zip silently truncates.
        # This is acceptable documented behavior — the truncated expression is lost.
        original = [
            make_expr("ON THE TABLE", 100.0, 115.0),
            make_expr("GOOD FAITH", 200.0, 215.0),
        ]
        # Claude only returns one item
        response = self.make_api_response([{
            "expression": "ON THE TABLE",
            "definition_en": "Available for consideration.",
            "explanation_kr": "협상에 올라온 상태.",
            "example_en": "All options are on the table.",
            "example_kr": "모든 선택지가 논의 대상입니다.",
            "keep": True,
        }])
        result = parse_enrichment_response(response, original)
        # Only the matched expression survives; second is silently dropped
        assert len(result) == 1
        assert result[0]["expression"] == "ON THE TABLE"
```

- [ ] **Step 3: Run tests to confirm they all fail**

```bash
pipenv run pytest tests/test_enrich_expressions.py -v
```

Expected: All tests fail with `ImportError: cannot import name 'filter_short_clips'`

- [ ] **Step 4: Commit the failing tests**

```bash
git add tests/__init__.py tests/test_enrich_expressions.py
git commit -m "test: add failing tests for filter_short_clips, build_prompt, parse_enrichment_response"
```

---

### Task 3: Implement `filter_short_clips`, `build_prompt`, `parse_enrichment_response`

**Files:**
- Create: `pipeline/enrich_expressions.py`

- [ ] **Step 1: Create `pipeline/enrich_expressions.py`**

Note: `import anthropic` is placed at the top with all other imports — do not place it mid-file.

```python
"""
Language Enrichment Module — enrich extracted expressions via Claude API.
Usage: python pipeline/enrich_expressions.py --in data/expressions_grouped.json --out data/expressions_enriched.json

For each expression group, calls Claude API once to:
  - Generate real definition_en, explanation_kr, example_en, example_kr
  - Filter out weak single-word picks (keep: false from Claude)
  - Discard expressions with source clip duration < MIN_SOURCE_DURATION
"""

import argparse
import anthropic
import json
import os
import sys

MIN_SOURCE_DURATION = 2.0  # seconds; expressions with duration <= this are discarded


def filter_short_clips(
    expressions: list[dict], min_duration: float = MIN_SOURCE_DURATION
) -> tuple[list[dict], list[dict]]:
    """Separate expressions into (valid, discarded) based on source clip duration.

    Args:
        expressions: List of expression dicts with 'start' and 'end' fields.
        min_duration: Minimum required source clip duration in seconds (exclusive).

    Returns:
        Tuple of (valid_expressions, discarded_expressions).
    """
    valid = []
    discarded = []
    for expr in expressions:
        duration = expr["end"] - expr["start"]
        if duration > min_duration:
            valid.append(expr)
        else:
            discarded.append(expr)
    return valid, discarded


def build_prompt(expressions: list[dict]) -> str:
    """Build the Claude prompt for enriching a group of expressions.

    Args:
        expressions: List of expression dicts (already duration-filtered).

    Returns:
        Prompt string for the Claude API call.
    """
    lines = []
    for i, expr in enumerate(expressions, 1):
        is_multi_word = len(expr["expression"].split()) > 1
        context = expr["original_sentence"][:300].replace("\n", " ")
        lines.append(
            f'{i}. Expression: "{expr["expression"]}"\n'
            f'   Context: "{context}"\n'
            f"   Multi-word expression: {str(is_multi_word).lower()}"
        )

    expr_block = "\n\n".join(lines)

    return f"""You are an English language teacher creating content for Korean learners of English (target level B2-C1).

For each expression below, return enrichment data as a JSON array — one object per expression, in the same order.

Each object must have exactly these fields:
- "expression": copy the expression text exactly from input
- "definition_en": 1-2 sentence English definition for B2-C1 learners
- "explanation_kr": Korean explanation (1-2 sentences, natural Korean)
- "example_en": a natural example sentence (different from the context provided)
- "example_kr": Korean translation of the example sentence
- "keep": true or false. For multi-word expressions, always true. For single-word terms, true only if the word is genuinely valuable to teach (idiomatic usage, commonly misunderstood, or high-frequency in formal English). Set false if it is basic general vocabulary not worth a dedicated lesson.
- "rejection_reason": brief English reason (only include this field if keep is false)

Return ONLY the JSON array. No markdown, no explanation, no code fences.

Expressions to enrich:

{expr_block}"""


def parse_enrichment_response(
    response_text: str, original_expressions: list[dict]
) -> list[dict]:
    """Parse Claude's JSON response and merge enrichment into original expressions.

    Filters out expressions where keep is false.
    If Claude returns fewer items than original_expressions, zip silently truncates
    (the unmatched originals are lost — this is acceptable documented behavior).
    Raises ValueError if the response cannot be parsed as JSON.

    Args:
        response_text: Raw text from Claude API response.
        original_expressions: Original expression dicts (pre-enrichment).

    Returns:
        List of enriched expression dicts with keep=false items removed.
    """
    text = response_text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        fenced = parts[1]
        if fenced.startswith("json"):
            fenced = fenced[4:]
        text = fenced.strip()

    try:
        enriched_data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse Claude response as JSON: {e}\nResponse: {text[:200]}"
        )

    result = []
    for orig, enr in zip(original_expressions, enriched_data):
        if not enr.get("keep", True):
            reason = enr.get("rejection_reason", "no reason given")
            print(f"    Rejected by Claude: {orig['expression']} — {reason}")
            continue
        merged = dict(orig)
        merged["definition_en"] = enr["definition_en"]
        merged["explanation_kr"] = enr["explanation_kr"]
        merged["example_en"] = enr["example_en"]
        merged["example_kr"] = enr["example_kr"]
        result.append(merged)
    return result
```

- [ ] **Step 2: Run the unit tests — all should pass now**

```bash
pipenv run pytest tests/test_enrich_expressions.py::TestFilterShortClips tests/test_enrich_expressions.py::TestBuildPrompt tests/test_enrich_expressions.py::TestParseEnrichmentResponse -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add pipeline/enrich_expressions.py
git commit -m "feat: implement filter_short_clips, build_prompt, parse_enrichment_response"
```

---

### Task 4: Write failing tests for `enrich_group` and `main`

**Files:**
- Modify: `tests/test_enrich_expressions.py`

- [ ] **Step 1: Append `enrich_group` and `main` tests to the test file**

Add these imports at the top of `tests/test_enrich_expressions.py` (after the existing imports):

```python
import anthropic
from pipeline.enrich_expressions import enrich_group, main
```

Then append these test classes at the bottom of the file:

```python
class TestEnrichGroup:
    def make_group(self, expressions):
        return {
            "group_id": "part1",
            "hook": {"en": "5 Must-Know Expressions", "kr": "필수 표현 5가지"},
            "closing": {"en": "Follow us!", "kr": "팔로우하세요!"},
            "expressions": expressions,
        }

    def _make_mock_client(self, mocker, response_text):
        mock_client = mocker.MagicMock()
        mock_client.messages.create.return_value.content = [
            mocker.MagicMock(text=response_text)
        ]
        return mock_client

    def test_enriches_valid_expressions(self, mocker):
        expressions = [
            make_expr("ON THE TABLE", 100.0, 115.0),
            make_expr("GOOD FAITH", 300.0, 320.0),
        ]
        group = self.make_group(expressions)
        response_text = json.dumps([
            {
                "expression": "ON THE TABLE",
                "definition_en": "Available for discussion.",
                "explanation_kr": "협상 중인 상태.",
                "example_en": "All options are on the table.",
                "example_kr": "모든 선택지가 논의 대상입니다.",
                "keep": True,
            },
            {
                "expression": "GOOD FAITH",
                "definition_en": "Honest intention to deal fairly.",
                "explanation_kr": "성실하고 정직한 의도.",
                "example_en": "They negotiated in good faith.",
                "example_kr": "그들은 성실하게 협상했습니다.",
                "keep": True,
            },
        ])
        mock_client = self._make_mock_client(mocker, response_text)
        result = enrich_group(mock_client, group, model="claude-haiku-4-5-20251001")
        assert len(result["expressions"]) == 2
        assert result["expressions"][0]["definition_en"] == "Available for discussion."
        assert result["expressions"][1]["explanation_kr"] == "성실하고 정직한 의도."

    def test_discards_short_clips_before_api_call(self, mocker):
        expressions = [
            make_expr("ON THE TABLE", 100.0, 115.0),   # valid
            make_expr("FILIBUSTER", 500.0, 500.01),    # too short — filtered before API
        ]
        group = self.make_group(expressions)
        response_text = json.dumps([{
            "expression": "ON THE TABLE",
            "definition_en": "Available for discussion.",
            "explanation_kr": "협상 중인 상태.",
            "example_en": "All options are on the table.",
            "example_kr": "모든 선택지가 논의 대상입니다.",
            "keep": True,
        }])
        mock_client = self._make_mock_client(mocker, response_text)
        result = enrich_group(mock_client, group, model="claude-haiku-4-5-20251001")
        # FILIBUSTER must not appear in the prompt sent to Claude
        call_args = mock_client.messages.create.call_args
        prompt_sent = call_args[1]["messages"][0]["content"]
        assert "FILIBUSTER" not in prompt_sent
        assert len(result["expressions"]) == 1

    def test_all_filtered_returns_empty_group_without_api_call(self, mocker):
        expressions = [make_expr("FILIBUSTER", 500.0, 500.01)]
        group = self.make_group(expressions)
        mock_client = mocker.MagicMock()
        result = enrich_group(mock_client, group, model="claude-haiku-4-5-20251001")
        mock_client.messages.create.assert_not_called()
        assert result["expressions"] == []
        # Other group fields must be preserved
        assert result["group_id"] == "part1"
        assert "hook" in result

    def test_api_error_propagates(self, mocker):
        expressions = [make_expr("ON THE TABLE", 100.0, 115.0)]
        group = self.make_group(expressions)
        mock_client = mocker.MagicMock()
        mock_client.messages.create.side_effect = anthropic.APIStatusError(
            message="rate limit", response=mocker.MagicMock(), body=None
        )
        with pytest.raises(anthropic.APIStatusError):
            enrich_group(mock_client, group, model="claude-haiku-4-5-20251001")

    def test_connection_error_propagates(self, mocker):
        expressions = [make_expr("ON THE TABLE", 100.0, 115.0)]
        group = self.make_group(expressions)
        mock_client = mocker.MagicMock()
        mock_client.messages.create.side_effect = anthropic.APIConnectionError(
            request=mocker.MagicMock()
        )
        with pytest.raises(anthropic.APIConnectionError):
            enrich_group(mock_client, group, model="claude-haiku-4-5-20251001")


class TestMain:
    def test_exits_nonzero_if_api_key_missing(self, tmp_path, mocker):
        input_file = tmp_path / "expressions_grouped.json"
        input_file.write_text(json.dumps({
            "title": "Test",
            "source_url": "",
            "total_expressions": 0,
            "groups": [],
        }))
        output_file = tmp_path / "out.json"
        mocker.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""})
        mocker.patch("sys.argv", [
            "enrich_expressions.py",
            "--in", str(input_file),
            "--out", str(output_file),
        ])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        assert not output_file.exists()

    def test_exits_nonzero_on_api_error_without_writing_output(self, tmp_path, mocker):
        input_file = tmp_path / "expressions_grouped.json"
        input_file.write_text(json.dumps({
            "title": "Test",
            "source_url": "",
            "total_expressions": 1,
            "groups": [{
                "group_id": "part1",
                "hook": {"en": "Hook", "kr": "훅"},
                "closing": {"en": "Close", "kr": "닫기"},
                "expressions": [make_expr("ON THE TABLE", 100.0, 115.0)],
            }],
        }))
        output_file = tmp_path / "out.json"
        mocker.patch.dict(os.environ, {
            "ANTHROPIC_API_KEY": "test-key",
            "PERFORMANCE_MODE": "LOW",
        })
        mocker.patch("sys.argv", [
            "enrich_expressions.py",
            "--in", str(input_file),
            "--out", str(output_file),
        ])
        mocker.patch(
            "pipeline.enrich_expressions.enrich_group",
            side_effect=anthropic.APIConnectionError(request=mocker.MagicMock()),
        )
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        assert not output_file.exists()
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
pipenv run pytest tests/test_enrich_expressions.py::TestEnrichGroup tests/test_enrich_expressions.py::TestMain -v
```

Expected: `ImportError` or `AttributeError` — `enrich_group` not yet implemented.

---

### Task 5: Implement `enrich_group` and `main`

**Files:**
- Modify: `pipeline/enrich_expressions.py`

- [ ] **Step 1: Append `enrich_group` and `main` to `pipeline/enrich_expressions.py`**

```python
def enrich_group(client: anthropic.Anthropic, group: dict, model: str) -> dict:
    """Enrich one expression group via Claude API.

    Filters short clips first, then calls Claude for remaining expressions.
    If all expressions are filtered before the API call, returns the group
    with an empty expressions list and makes no API call.

    Args:
        client: Anthropic API client.
        group: Single group dict from expressions_grouped.json.
        model: Claude model ID to use.

    Returns:
        Group dict with enriched expressions. Preserves all non-expression fields.

    Raises:
        anthropic.APIError / APIConnectionError / RateLimitError on API failure.
        ValueError if the API response cannot be parsed.
    """
    expressions = group["expressions"]

    valid, discarded = filter_short_clips(expressions)
    for d in discarded:
        dur = round(d["end"] - d["start"], 3)
        print(f"    Discarded (source clip {dur}s < {MIN_SOURCE_DURATION}s): {d['expression']}")

    if not valid:
        print(f"    Warning: all expressions discarded for {group['group_id']} — empty group")
        return {**group, "expressions": []}

    prompt = build_prompt(valid)

    message = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text
    enriched_expressions = parse_enrichment_response(response_text, valid)

    remaining = len(enriched_expressions)
    if remaining < 3:
        print(
            f"    Warning: {group['group_id']} has only {remaining} expression(s) "
            f"after enrichment (started with {len(expressions)})"
        )

    return {**group, "expressions": enriched_expressions}


def main():
    parser = argparse.ArgumentParser(description="Enrich expressions via Claude API")
    parser.add_argument("--in", dest="input", required=True, help="Input expressions_grouped.json")
    parser.add_argument("--out", required=True, help="Output expressions_enriched.json")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set", file=sys.stderr)
        sys.exit(1)

    performance_mode = os.environ.get("PERFORMANCE_MODE", "LOW").upper()
    model = (
        "claude-haiku-4-5-20251001" if performance_mode == "LOW" else "claude-sonnet-4-6"
    )
    print(f"  Model: {model} (PERFORMANCE_MODE={performance_mode})")

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    groups = data.get("groups", [])
    if not groups:
        print("ERROR: No groups found in input file", file=sys.stderr)
        sys.exit(1)

    print(f"  Enriching {len(groups)} groups...")

    client = anthropic.Anthropic(api_key=api_key)
    enriched_groups = []

    for group in groups:
        print(f"  Group: {group['group_id']} ({len(group['expressions'])} expressions)")
        try:
            enriched = enrich_group(client, group, model=model)
        except (
            anthropic.APIError,         # covers 4xx/5xx and RateLimitError subclasses
            anthropic.APIConnectionError,  # network failures — not a subclass of APIError
        ) as e:
            print(
                f"ERROR: Claude API call failed for {group['group_id']}: {e}",
                file=sys.stderr,
            )
            sys.exit(1)
        except ValueError as e:
            print(
                f"ERROR: Failed to parse Claude response for {group['group_id']}: {e}",
                file=sys.stderr,
            )
            sys.exit(1)
        enriched_groups.append(enriched)

    total = sum(len(g["expressions"]) for g in enriched_groups)

    output = {
        "title": data.get("title", ""),
        "source_url": data.get("source_url", ""),
        "total_expressions": total,
        "groups": enriched_groups,
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    # Write only after all groups succeed — no partial output on error
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  Output: {args.out} ({total} expressions in {len(enriched_groups)} groups)")
    for g in enriched_groups:
        exprs = ", ".join(e["expression"] for e in g["expressions"])
        print(f"    {g['group_id']}: {exprs or '(empty)'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run all tests**

```bash
pipenv run pytest tests/test_enrich_expressions.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add pipeline/enrich_expressions.py tests/test_enrich_expressions.py
git commit -m "feat: implement enrich_expressions.py with Claude API enrichment and duration filter"
```

---

## Chunk 2: QA Validator + Pipeline Wiring

### Task 6: Write failing tests for `min_source_duration` QA rule

**Files:**
- Create: `tests/test_qa_validator.py`

- [ ] **Step 1: Create test file**

Create `tests/test_qa_validator.py`:

```python
"""Tests for the min_source_duration backstop rule in qa_validator.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.qa_validator import validate_and_fix_part


def make_clip(start, end, clip_type="expression_raw", clip_start_sec=None, clip_end_sec=None):
    clip = {
        "start": start,
        "end": end,
        "type": clip_type,
        "overlay": {"en": "Test overlay", "kr": "테스트"},
    }
    if clip_start_sec is not None:
        clip["clipStartSec"] = clip_start_sec
    if clip_end_sec is not None:
        clip["clipEndSec"] = clip_end_sec
    return clip


class TestMinSourceDurationRule:
    def make_part(self, clips):
        return {"id": "part1", "clips": clips}

    def test_valid_source_clip_passes(self):
        clips = [make_clip(0.0, 5.0, clip_start_sec=100.0, clip_end_sec=115.0)]
        fixed_part, issues = validate_and_fix_part(self.make_part(clips))
        duration_issues = [i for i in issues if i["rule"] == "min_source_duration"]
        assert len(duration_issues) == 0
        assert len(fixed_part["clips"]) == 1

    def test_zero_length_source_clip_is_discarded(self):
        clips = [make_clip(0.0, 5.0, clip_start_sec=1196.789, clip_end_sec=1196.799)]
        fixed_part, issues = validate_and_fix_part(self.make_part(clips))
        duration_issues = [i for i in issues if i["rule"] == "min_source_duration"]
        assert len(duration_issues) == 1
        assert duration_issues[0]["auto_fixed"] is True
        assert len(fixed_part["clips"]) == 0

    def test_source_clip_at_threshold_is_discarded(self):
        # clipEndSec - clipStartSec == 1.0 is discarded (must be strictly > 1.0)
        clips = [make_clip(0.0, 5.0, clip_start_sec=100.0, clip_end_sec=101.0)]
        fixed_part, issues = validate_and_fix_part(self.make_part(clips))
        duration_issues = [i for i in issues if i["rule"] == "min_source_duration"]
        assert len(duration_issues) == 1

    def test_source_clip_just_above_threshold_passes(self):
        clips = [make_clip(0.0, 5.0, clip_start_sec=100.0, clip_end_sec=101.001)]
        fixed_part, issues = validate_and_fix_part(self.make_part(clips))
        duration_issues = [i for i in issues if i["rule"] == "min_source_duration"]
        assert len(duration_issues) == 0

    def test_clips_without_source_fields_are_not_checked(self):
        # hook/wrapup clips have no clipStartSec/clipEndSec — must not be checked
        clips = [
            make_clip(0.0, 3.0, clip_type="hook"),
            make_clip(3.0, 8.0, clip_type="wrapup"),
        ]
        fixed_part, issues = validate_and_fix_part(self.make_part(clips))
        duration_issues = [i for i in issues if i["rule"] == "min_source_duration"]
        assert len(duration_issues) == 0
        assert len(fixed_part["clips"]) == 2
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pipenv run pytest tests/test_qa_validator.py -v
```

Expected: All `TestMinSourceDurationRule` tests fail — rule not yet implemented.

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_qa_validator.py
git commit -m "test: add failing tests for min_source_duration QA backstop rule"
```

---

### Task 7: Implement `min_source_duration` rule in `qa_validator.py`

**Files:**
- Modify: `pipeline/qa_validator.py`

- [ ] **Step 1: Add `MIN_BACKSTOP_SOURCE_DURATION` at module scope**

Open `pipeline/qa_validator.py`. Find the existing module-level constants (lines 18–20):

```python
MAX_LINES = 2
MAX_CHARS_PER_LINE = 42
MAX_DURATION = 180.0
```

Add the new constant immediately after:

```python
MIN_BACKSTOP_SOURCE_DURATION = 1.0  # seconds; backstop for near-zero source clips
```

- [ ] **Step 2: Insert the `min_source_duration` check inside the loop**

Find the comment inside `validate_and_fix_part`'s `for i, clip in enumerate(part["clips"]):` loop:

```python
        # Validate and fix overlay text
        if "overlay" in fixed_clip:
```

Insert the following block immediately before it:

```python
        # Backstop: discard clips with near-zero source video duration.
        # Primary filter is in enrich_expressions.py — this should rarely trigger.
        if "clipStartSec" in fixed_clip and "clipEndSec" in fixed_clip:
            source_duration = fixed_clip["clipEndSec"] - fixed_clip["clipStartSec"]
            if source_duration <= MIN_BACKSTOP_SOURCE_DURATION:
                issues.append({
                    "part": part_id,
                    "clip": i,
                    "field": "clipStartSec/clipEndSec",
                    "rule": "min_source_duration",
                    "detail": (
                        f"source clip {source_duration:.3f}s "
                        f"(min {MIN_BACKSTOP_SOURCE_DURATION}s) — clip dropped"
                    ),
                    "auto_fixed": True,
                })
                continue  # skip appending this clip to fixed_clips
```

- [ ] **Step 3: Run QA validator tests**

```bash
pipenv run pytest tests/test_qa_validator.py -v
```

Expected: All tests PASS.

- [ ] **Step 4: Run full test suite — no regressions**

```bash
pipenv run pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/qa_validator.py
git commit -m "feat: add min_source_duration backstop rule to qa_validator"
```

---

### Task 8: Update `run_pipeline.sh`

**Files:**
- Modify: `run_pipeline.sh`

- [ ] **Step 1: Add `ANTHROPIC_API_KEY` hard-fail check**

In `run_pipeline.sh`, find the existing env var validation block:

```bash
if [ -z "${YT_VIDEO_URL:-}" ]; then
  echo "ERROR: YT_VIDEO_URL is not set in .env"
  exit 1
fi
```

Add immediately after it:

```bash
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ERROR: ANTHROPIC_API_KEY is not set in .env (needed for expression enrichment)"
  exit 1
fi
```

- [ ] **Step 2: Add Step 2.5 between Step 2 and Step 3**

Find the line:

```bash
step "3" "Generating clip definitions (expressions_to_clips.py)"
```

Insert the following block immediately before it:

```bash
step "2.5" "Enriching expressions via Claude API (enrich_expressions.py)"

$PYTHON pipeline/enrich_expressions.py \
  --in data/expressions_grouped.json \
  --out data/expressions_enriched.json

[ -f data/expressions_enriched.json ] || fail "data/expressions_enriched.json was not created"
success "data/expressions_enriched.json created"

```

- [ ] **Step 3: Update Step 3 to read from `expressions_enriched.json`**

In the Step 3 block, change:

```bash
$PYTHON pipeline/expressions_to_clips.py \
  --in data/expressions_grouped.json \
  --out data/clips.json
```

To:

```bash
$PYTHON pipeline/expressions_to_clips.py \
  --in data/expressions_enriched.json \
  --out data/clips.json
```

- [ ] **Step 4: Verify no syntax errors**

```bash
bash -n run_pipeline.sh
```

Expected: No output (clean).

- [ ] **Step 5: Commit**

```bash
git add run_pipeline.sh
git commit -m "feat: wire enrich_expressions.py into pipeline as Step 2.5"
```

---

### Task 9: Update `.env.example`

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add `ANTHROPIC_API_KEY` entry**

Add after the `PERFORMANCE_MODE` line:

```bash
# Claude API — required for expression enrichment (Step 2.5)
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "chore: add ANTHROPIC_API_KEY to .env.example"
```

---

### Task 10: Smoke test

- [ ] **Step 1: Full test suite**

```bash
pipenv run pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 2: Shell syntax check**

```bash
bash -n run_pipeline.sh && echo "Syntax OK"
```

Expected: `Syntax OK`

- [ ] **Step 3: Verify missing API key fails cleanly with no output file**

```bash
ANTHROPIC_API_KEY="" pipenv run python pipeline/enrich_expressions.py \
  --in data/expressions_grouped.json \
  --out /tmp/should_not_exist.json
echo "Exit code: $?"
ls /tmp/should_not_exist.json 2>/dev/null && echo "FILE EXISTS (bad)" || echo "No file written (good)"
```

Expected:
```
ERROR: ANTHROPIC_API_KEY is not set
Exit code: 1
No file written (good)
```

- [ ] **Step 4: Review final commit log**

```bash
git log --oneline -8
```

Confirm all commits are present and in order.
