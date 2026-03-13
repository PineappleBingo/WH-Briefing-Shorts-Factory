"""
Language Analysis Module — extract key English expressions from transcript.
Usage: python pipeline/extract_expressions.py --in data/transcript.json --out data/expressions_grouped.json

Heuristic extraction: scores sentences by linguistic complexity,
selects top candidates, and groups them into sets of 5 for Shorts production.
Korean translations are placeholders — the Analyst Agent refines them.
"""

import argparse
import json
import math
import os
import re
import sys

# High-value phrasal verbs, idioms, and collocations common in WH briefings
EXPRESSION_PATTERNS = [
    r"\bcall into question\b",
    r"\bdouble down\b",
    r"\bpush back\b",
    r"\broll out\b",
    r"\bweigh in\b",
    r"\blay out\b",
    r"\bramp up\b",
    r"\bscale back\b",
    r"\bstand by\b",
    r"\bfollow through\b",
    r"\bhold accountable\b",
    r"\bunderscore\b",
    r"\breiterate\b",
    r"\bleverage\b",
    r"\bpivot\b",
    r"\bmandate\b",
    r"\bbipartisan\b",
    r"\bunprecedented\b",
    r"\blandmark\b",
    r"\bstakeholder\b",
    r"\btransparency\b",
    r"\baccountability\b",
    r"\bescalation\b",
    r"\bde-escalat\b",
    r"\bsanctions?\b",
    r"\btariffs?\b",
    r"\bexecutive order\b",
    r"\bnational security\b",
    r"\bforeign policy\b",
    r"\bfiscal\b",
    r"\bdeficit\b",
    r"\binflation\b",
    r"\bappropriat\b",
    r"\bin light of\b",
    r"\bwith respect to\b",
    r"\bin terms of\b",
    r"\bat the end of the day\b",
    r"\bmake no mistake\b",
    r"\bthe fact of the matter\b",
    r"\brest assured\b",
    r"\bon the table\b",
    r"\bacross the aisle\b",
    r"\bbehind closed doors\b",
]

# Highlight colors cycled per expression
HIGHLIGHT_COLORS = [
    "#00BFFF",  # Deep Sky Blue
    "#FFD700",  # Gold
    "#FF6B6B",  # Coral Red
    "#7B68EE",  # Medium Slate Blue
    "#00FA9A",  # Medium Spring Green
]


def score_sentence(text: str) -> float:
    """Score a sentence by linguistic interest for B2-C1 learners."""
    score = 0.0
    words = text.split()
    word_count = len(words)

    # Skip very short or very long sentences
    if word_count < 5:
        return 0.0
    if word_count > 60:
        return 0.0

    # Prefer medium-length sentences (10-30 words)
    if 10 <= word_count <= 30:
        score += 2.0

    # Check for high-value patterns
    text_lower = text.lower()
    for pattern in EXPRESSION_PATTERNS:
        if re.search(pattern, text_lower):
            score += 5.0

    # Bonus for longer average word length (indicates complex vocabulary)
    avg_word_len = sum(len(w) for w in words) / word_count
    if avg_word_len > 5.5:
        score += 2.0

    # Bonus for subordinate clauses (commas suggest complex structure)
    comma_count = text.count(",")
    if 1 <= comma_count <= 3:
        score += 1.0

    # Penalize questions (often filler from reporters)
    if text.strip().endswith("?"):
        score -= 2.0

    # Penalize common filler phrases
    fillers = ["thank you", "good morning", "good afternoon", "good evening",
               "ladies and gentlemen", "next question", "go ahead"]
    for filler in fillers:
        if filler in text_lower:
            score -= 5.0

    return max(score, 0.0)


def extract_expression_from_sentence(text: str) -> str:
    """Extract the most notable expression/phrase from a sentence."""
    text_lower = text.lower()

    # First check for known multi-word expressions
    for pattern in EXPRESSION_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(0).upper().strip()

    # Fallback: extract the longest "interesting" word (6+ chars, not common)
    common_words = {
        "the", "and", "that", "this", "with", "from", "have", "been",
        "will", "would", "could", "should", "their", "there", "about",
        "which", "these", "those", "other", "after", "before", "because",
        "through", "between", "going", "president", "united", "states",
        "administration", "government", "important", "american", "country",
    }
    words = re.findall(r"[a-zA-Z]+", text)
    candidates = [w for w in words if len(w) >= 6 and w.lower() not in common_words]

    if candidates:
        # Pick the longest
        best = max(candidates, key=len)
        return best.upper()

    return text.split()[0].upper() if text.split() else "EXPRESSION"


def group_expressions(scored_sentences: list[dict], group_size: int = 5) -> list[dict]:
    """Group top-scored sentences into sets of 5 for Shorts production."""
    # Sort by score descending
    ranked = sorted(scored_sentences, key=lambda x: x["score"], reverse=True)

    # Select top candidates (15-20, then trim to nearest multiple of group_size)
    max_candidates = 20
    candidates = ranked[:max_candidates]

    # Trim to exact multiple of group_size
    num_groups = max(1, len(candidates) // group_size)
    candidates = candidates[:num_groups * group_size]

    # Re-sort by timestamp for chronological ordering within groups
    candidates.sort(key=lambda x: x["start"])

    groups = []
    for g in range(num_groups):
        group_items = candidates[g * group_size:(g + 1) * group_size]
        group_id = f"part{g + 1}"

        expressions = []
        for i, item in enumerate(group_items):
            expr_text = extract_expression_from_sentence(item["text"])
            color = HIGHLIGHT_COLORS[i % len(HIGHLIGHT_COLORS)]

            expressions.append({
                "expression": expr_text,
                "original_sentence": item["text"],
                "start": item["start"],
                "end": item["end"],
                "definition_en": f"[Definition of '{expr_text.lower()}']",
                "explanation_kr": f"['{expr_text.lower()}'의 한국어 설명]",
                "example_en": f"[Example sentence using '{expr_text.lower()}']",
                "example_kr": "[예문 한국어 번역]",
                "cefr_level": "B2",
                "highlight_color": color,
            })

        # Hook uses the highest-scored expression in this group
        best_in_group = max(group_items, key=lambda x: x["score"])
        best_expr = extract_expression_from_sentence(best_in_group["text"])

        groups.append({
            "group_id": group_id,
            "hook": {
                "en": f"5 Key Expressions from Today's Briefing",
                "kr": "오늘 브리핑의 핵심 표현 5가지",
            },
            "closing": {
                "en": "Like & Subscribe for more!",
                "kr": "좋아요와 구독 부탁드려요!",
            },
            "expressions": expressions,
        })

    return groups


def main():
    parser = argparse.ArgumentParser(description="Extract key expressions from transcript")
    parser.add_argument("--in", dest="input", required=True, help="Input transcript JSON")
    parser.add_argument("--out", required=True, help="Output grouped expressions JSON")
    args = parser.parse_args()

    # Load transcript
    with open(args.input, "r", encoding="utf-8") as f:
        transcript = json.load(f)

    sentences = transcript.get("sentences", [])
    if not sentences:
        print("ERROR: No sentences found in transcript", file=sys.stderr)
        sys.exit(1)

    print(f"  Scoring {len(sentences)} sentences...")

    # Score each sentence
    scored = []
    for s in sentences:
        sc = score_sentence(s["text"])
        if sc > 0:
            scored.append({
                "text": s["text"],
                "start": s["start"],
                "end": s["end"],
                "score": sc,
            })

    print(f"  Candidates with score > 0: {len(scored)}")

    if len(scored) < 5:
        print("WARNING: Fewer than 5 scorable sentences — output may be incomplete", file=sys.stderr)
        # Pad with remaining sentences sorted by length
        remaining = [s for s in sentences if score_sentence(s["text"]) == 0]
        remaining.sort(key=lambda x: len(x["text"]), reverse=True)
        for s in remaining[:5 - len(scored)]:
            scored.append({
                "text": s["text"],
                "start": s["start"],
                "end": s["end"],
                "score": 0.1,
            })

    # Group into sets of 5
    groups = group_expressions(scored)
    print(f"  Groups created: {len(groups)}")

    # Build output
    output = {
        "title": transcript.get("title", ""),
        "source_url": transcript.get("source_url", ""),
        "total_expressions": sum(len(g["expressions"]) for g in groups),
        "groups": groups,
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  Output: {args.out} ({output['total_expressions']} expressions in {len(groups)} groups)")


if __name__ == "__main__":
    main()
