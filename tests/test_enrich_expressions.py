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
