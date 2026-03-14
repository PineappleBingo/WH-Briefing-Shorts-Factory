"""
Language Analysis Module — extract key English expressions from transcript.
Usage: python pipeline/extract_expressions.py --in data/transcript.json --out data/expressions_grouped.json

Heuristic extraction: matches sentences against a curated list of multi-word
expressions (phrasal verbs, idioms, collocations) common in WH briefings.
Only sentences containing recognized patterns are selected.
Korean translations are placeholders — the Analyst Agent refines them.
"""

import argparse
import json
import os
import re
import sys

# Multi-word expressions: phrasal verbs, idioms, collocations, and policy terms
# Each entry: (pattern, display_form, cefr_level)
# Only multi-word or advanced single-word expressions — no common nouns
EXPRESSION_CATALOG = [
    # Phrasal verbs
    (r"\bcall(?:ed|s|ing)? into question\b", "CALL INTO QUESTION", "C1"),
    (r"\bdoubl(?:e|ed|ing) down\b", "DOUBLE DOWN", "B2"),
    (r"\bpush(?:ed|es|ing)? back\b", "PUSH BACK", "B2"),
    (r"\broll(?:ed|s|ing)? out\b", "ROLL OUT", "B2"),
    (r"\bweigh(?:ed|s|ing)? in\b", "WEIGH IN", "B2"),
    (r"\bla(?:y|id|ying) out\b", "LAY OUT", "B2"),
    (r"\bramp(?:ed|s|ing)? up\b", "RAMP UP", "B2"),
    (r"\bscal(?:e|ed|ing) back\b", "SCALE BACK", "B2"),
    (r"\bstand(?:s|ing)? by\b", "STAND BY", "B2"),
    (r"\bfollow(?:ed|s|ing)? through\b", "FOLLOW THROUGH", "B2"),
    (r"\bhold(?:s|ing)? (?:\w+ )?accountable\b", "HOLD ACCOUNTABLE", "B2"),
    (r"\bcrack(?:ed|s|ing)? down\b", "CRACK DOWN", "B2"),
    (r"\bphase(?:d|s|ing)? out\b", "PHASE OUT", "B2"),
    (r"\brul(?:e|ed|ing) out\b", "RULE OUT", "B2"),
    (r"\bcarr(?:y|ied|ying) out\b", "CARRY OUT", "B2"),
    (r"\bbring(?:s|ing)? to the table\b", "BRING TO THE TABLE", "C1"),
    (r"\bstep(?:ped|s|ping)? up\b", "STEP UP", "B2"),
    (r"\bback(?:ed|s|ing)? off\b", "BACK OFF", "B2"),
    (r"\bbail(?:ed|s|ing)? out\b", "BAIL OUT", "B2"),
    (r"\bshut(?:s|ting)? down\b", "SHUT DOWN", "B2"),
    (r"\bwater(?:ed|s|ing)? down\b", "WATER DOWN", "C1"),
    (r"\bfall(?:s|ing)? short\b", "FALL SHORT", "B2"),

    # Idioms and fixed phrases
    (r"\bin light of\b", "IN LIGHT OF", "B2"),
    (r"\bwith respect to\b", "WITH RESPECT TO", "B2"),
    (r"\bin terms of\b", "IN TERMS OF", "B2"),
    (r"\bat the end of the day\b", "AT THE END OF THE DAY", "B2"),
    (r"\bmake no mistake\b", "MAKE NO MISTAKE", "C1"),
    (r"\bthe fact of the matter\b", "THE FACT OF THE MATTER", "B2"),
    (r"\brest assured\b", "REST ASSURED", "C1"),
    (r"\bon the table\b", "ON THE TABLE", "B2"),
    (r"\bacross the aisle\b", "ACROSS THE AISLE", "C1"),
    (r"\bbehind closed doors\b", "BEHIND CLOSED DOORS", "B2"),
    (r"\bthe bottom line\b", "THE BOTTOM LINE", "B2"),
    (r"\bin the wake of\b", "IN THE WAKE OF", "C1"),
    (r"\bpave the way\b", "PAVE THE WAY", "C1"),
    (r"\bturn(?:s|ed|ing)? a blind eye\b", "TURN A BLIND EYE", "C1"),
    (r"\bdraw(?:s|n|ing)? the line\b", "DRAW THE LINE", "B2"),
    (r"\btake(?:s|n|ing)? a stance\b", "TAKE A STANCE", "B2"),
    (r"\bget(?:s|ting)? to the bottom of\b", "GET TO THE BOTTOM OF", "B2"),
    (r"\bin no uncertain terms\b", "IN NO UNCERTAIN TERMS", "C1"),
    (r"\bset(?:s|ting)? the record straight\b", "SET THE RECORD STRAIGHT", "C1"),
    (r"\bbear(?:s|ing)? in mind\b", "BEAR IN MIND", "B2"),
    (r"\btake(?:s|n|ing)? into account\b", "TAKE INTO ACCOUNT", "B2"),
    (r"\bfor the sake of\b", "FOR THE SAKE OF", "B2"),
    (r"\bby and large\b", "BY AND LARGE", "C1"),
    (r"\ba matter of\b", "A MATTER OF", "B2"),

    # Advanced policy/political vocabulary (single-word but high-value for learners)
    (r"\bunderscore[ds]?\b", "UNDERSCORE", "C1"),
    (r"\breiterate[ds]?\b", "REITERATE", "C1"),
    (r"\bleverage[ds]?\b", "LEVERAGE", "C1"),
    (r"\bmandate[ds]?\b", "MANDATE", "B2"),
    (r"\bbipartisan\b", "BIPARTISAN", "C1"),
    (r"\bunprecedented\b", "UNPRECEDENTED", "C1"),
    (r"\blandmark\b", "LANDMARK", "C1"),
    (r"\btransparency\b", "TRANSPARENCY", "B2"),
    (r"\baccountability\b", "ACCOUNTABILITY", "B2"),
    (r"\bescalation\b", "ESCALATION", "B2"),
    (r"\bde-escalat(?:e|ion|ing)\b", "DE-ESCALATION", "C1"),
    (r"\bsanctions\b", "SANCTIONS", "B2"),
    (r"\btariffs?\b", "TARIFF(S)", "B2"),
    (r"\bfiscal\b", "FISCAL", "C1"),
    (r"\bdeficit\b", "DEFICIT", "B2"),
    (r"\binflation\b", "INFLATION", "B2"),
    (r"\bfilibuster\b", "FILIBUSTER", "C1"),
    (r"\bjurisdiction\b", "JURISDICTION", "C1"),
    (r"\breciprocal\b", "RECIPROCAL", "C1"),
    (r"\bunilateral(?:ly)?\b", "UNILATERAL", "C1"),
    (r"\bmultilateral(?:ly)?\b", "MULTILATERAL", "C1"),
    (r"\bexecutive order\b", "EXECUTIVE ORDER", "B2"),
    (r"\bnational security\b", "NATIONAL SECURITY", "B2"),
    (r"\bforeign policy\b", "FOREIGN POLICY", "B2"),
    (r"\bdue process\b", "DUE PROCESS", "C1"),
    (r"\bcheck(?:s)? and balance(?:s)?\b", "CHECKS AND BALANCES", "C1"),
    (r"\brule of law\b", "RULE OF LAW", "B2"),
    (r"\bseparation of powers\b", "SEPARATION OF POWERS", "C1"),
    (r"\bgood faith\b", "GOOD FAITH", "B2"),
    (r"\bbad faith\b", "BAD FAITH", "B2"),
    (r"\bstatus quo\b", "STATUS QUO", "C1"),
    (r"\bquid pro quo\b", "QUID PRO QUO", "C1"),
    (r"\bdiplomacy\b", "DIPLOMACY", "B2"),
    (r"\bdeterrence\b", "DETERRENCE", "C1"),
    (r"\bcoalition\b", "COALITION", "B2"),
    (r"\bappropriation\b", "APPROPRIATION", "C1"),
    (r"\bimpeach(?:ment)?\b", "IMPEACHMENT", "C1"),
    (r"\bveto\b", "VETO", "B2"),
    (r"\bramification\b", "RAMIFICATION", "C1"),
    (r"\boverhaul\b", "OVERHAUL", "C1"),
    (r"\bcease-?fire\b", "CEASEFIRE", "B2"),
]

# Highlight colors cycled per expression
HIGHLIGHT_COLORS = [
    "#00BFFF",  # Deep Sky Blue
    "#FFD700",  # Gold
    "#FF6B6B",  # Coral Red
    "#7B68EE",  # Medium Slate Blue
    "#00FA9A",  # Medium Spring Green
]


def find_expressions_in_sentence(text: str) -> list[tuple[str, str, str]]:
    """Find all catalog expressions in a sentence.
    Returns list of (matched_text, display_form, cefr_level)."""
    text_lower = text.lower()
    found = []
    for pattern, display, cefr in EXPRESSION_CATALOG:
        if re.search(pattern, text_lower):
            found.append((pattern, display, cefr))
    return found


def score_sentence(text: str) -> tuple[float, list[tuple[str, str, str]]]:
    """Score a sentence by expression matches. Returns (score, matched_expressions)."""
    words = text.split()
    word_count = len(words)

    # Skip very short sentences
    if word_count < 3:
        return 0.0, []

    # Only score sentences that contain at least one catalog expression
    matches = find_expressions_in_sentence(text)
    if not matches:
        return 0.0, []

    score = 0.0

    # Penalize very long sentences (merged VTT cues) — still usable but less ideal
    if word_count > 60:
        score -= 2.0

    # Base score per expression match (multi-word expressions score higher)
    for _, display, cefr in matches:
        word_count_expr = len(display.split())
        if word_count_expr >= 3:
            score += 8.0  # Idioms/phrases (3+ words)
        elif word_count_expr == 2:
            score += 6.0  # Phrasal verbs / collocations
        else:
            score += 3.0  # Advanced single words

        # Bonus for C1 level
        if cefr == "C1":
            score += 1.0

    # Prefer medium-length sentences (10-30 words) — good for subtitles
    if 10 <= word_count <= 30:
        score += 1.0

    # Penalize questions (often from reporters, not the speaker)
    if text.strip().endswith("?"):
        score -= 2.0

    # Penalize common filler phrases
    fillers = ["thank you", "good morning", "good afternoon", "good evening",
               "ladies and gentlemen", "next question", "go ahead"]
    text_lower = text.lower()
    for filler in fillers:
        if filler in text_lower:
            score -= 5.0

    return max(score, 0.0), matches


def group_expressions(scored_sentences: list[dict], group_size: int = 5) -> list[dict]:
    """Group top-scored sentences into sets of 5 for Shorts production.
    Deduplicates by expression display form."""
    # Sort by score descending
    ranked = sorted(scored_sentences, key=lambda x: x["score"], reverse=True)

    # Deduplicate: pick the best sentence for each unique expression
    seen_expressions = set()
    unique = []
    for item in ranked:
        # Use the primary (first) expression as the dedup key
        expr_display = item["expression"]
        if expr_display in seen_expressions:
            continue
        seen_expressions.add(expr_display)
        unique.append(item)

    # Select up to 20, trim to nearest multiple of group_size
    max_candidates = 20
    candidates = unique[:max_candidates]
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
            color = HIGHLIGHT_COLORS[i % len(HIGHLIGHT_COLORS)]
            expr_text = item["expression"]
            cefr = item["cefr_level"]

            expressions.append({
                "expression": expr_text,
                "original_sentence": item["text"],
                "start": item["start"],
                "end": item["end"],
                "definition_en": f"[Definition of '{expr_text.lower()}']",
                "explanation_kr": f"['{expr_text.lower()}'의 한국어 설명]",
                "example_en": f"[Example sentence using '{expr_text.lower()}']",
                "example_kr": "[예문 한국어 번역]",
                "cefr_level": cefr,
                "highlight_color": color,
            })

        groups.append({
            "group_id": group_id,
            "hook": {
                "en": "5 Must-Know WH Briefing Expressions",
                "kr": "백악관 브리핑 필수 표현 5가지",
            },
            "closing": {
                "en": "Follow for daily real-world English!",
                "kr": "매일 실전 영어 표현을 받아보세요!",
            },
            "expressions": expressions,
        })

    return groups


def main():
    parser = argparse.ArgumentParser(description="Extract key expressions from transcript")
    parser.add_argument("--in", dest="input", required=True, help="Input transcript JSON")
    parser.add_argument("--out", required=True, help="Output grouped expressions JSON")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        transcript = json.load(f)

    sentences = transcript.get("sentences", [])
    if not sentences:
        print("ERROR: No sentences found in transcript", file=sys.stderr)
        sys.exit(1)

    print(f"  Scoring {len(sentences)} sentences...")

    # Score each sentence — only those with catalog expression matches
    scored = []
    for s in sentences:
        sc, matches = score_sentence(s["text"])
        if sc > 0 and matches:
            # Use the highest-value expression found in this sentence
            # Prefer multi-word expressions over single words
            best_match = max(matches, key=lambda m: len(m[1].split()))
            scored.append({
                "text": s["text"],
                "start": s["start"],
                "end": s["end"],
                "score": sc,
                "expression": best_match[1],  # display form
                "cefr_level": best_match[2],
            })

    print(f"  Sentences with expression matches: {len(scored)}")

    if len(scored) < 5:
        print(f"WARNING: Only {len(scored)} matches — need at least 5 for one group", file=sys.stderr)
        if len(scored) == 0:
            print("ERROR: No expressions found in transcript", file=sys.stderr)
            sys.exit(1)

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

    total = output["total_expressions"]
    print(f"  Output: {args.out} ({total} expressions in {len(groups)} groups)")

    # Print summary
    for g in groups:
        print(f"    {g['group_id']}: {', '.join(e['expression'] for e in g['expressions'])}")


if __name__ == "__main__":
    main()
