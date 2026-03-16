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
