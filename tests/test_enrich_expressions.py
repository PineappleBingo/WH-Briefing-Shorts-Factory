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

import anthropic
from pipeline.enrich_expressions import enrich_group, main


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
