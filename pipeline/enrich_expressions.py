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
        anthropic.APIError / APIConnectionError on API failure.
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
