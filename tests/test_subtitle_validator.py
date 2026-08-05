"""Subtitle validation: defects, warnings, auto-fix."""

import pytest

from src.subtitles.exceptions import InvalidCueError
from src.subtitles.model import SubtitleCue
from src.subtitles.validator import SubtitleValidator


def _validator(**kwargs) -> SubtitleValidator:
    defaults = dict(reading_speed_cps=21.0, max_chars_per_line=42, max_lines=2)
    defaults.update(kwargs)
    return SubtitleValidator(**defaults)


def test_clean_document_has_no_issues():
    validator = _validator()
    cues = [SubtitleCue(0.0, 2.0, "A reasonable caption.")]
    assert validator.validate(cues) == []
    assert validator.is_valid(cues)


def test_overlap_is_error():
    validator = _validator()
    cues = [SubtitleCue(0.0, 2.0, "first"), SubtitleCue(1.5, 3.0, "second")]
    issues = validator.validate(cues)
    overlap_issues = [issue for issue in issues if issue.code == "overlap"]
    assert overlap_issues  # reported at least once
    assert len(overlap_issues) == 1  # and not duplicated


def test_negative_duration_is_impossible_to_build():
    with pytest.raises(InvalidCueError):
        SubtitleCue(2.0, 1.0)


def test_empty_caption_is_error():
    validator = _validator()
    issues = validator.validate([SubtitleCue(0.0, 1.0, "   ")])
    assert any(issue.code == "empty_text" and issue.severity == "error" for issue in issues)


def test_empty_document_is_error():
    validator = _validator()
    issues = validator.validate([])
    assert any(issue.code == "empty_document" for issue in issues)


def test_reading_speed_warning():
    validator = _validator(reading_speed_cps=21.0)
    issues = validator.validate([SubtitleCue(0.0, 1.0, "x" * 40)])  # 40 cps
    assert any(issue.code == "reading_speed" and issue.severity == "warning" for issue in issues)


def test_line_too_long_warning():
    validator = _validator(max_chars_per_line=20)
    issues = validator.validate([SubtitleCue(0.0, 5.0, "x" * 30)])
    assert any(issue.code == "line_too_long" for issue in issues)


def test_too_many_lines_warning():
    validator = _validator(max_lines=2)
    issues = validator.validate([SubtitleCue(0.0, 5.0, "a\nb\nc")])
    assert any(issue.code == "too_many_lines" for issue in issues)


def test_lenient_strictness_filters_warnings():
    validator = _validator(strictness="lenient", max_chars_per_line=10)
    issues = validator.validate([SubtitleCue(0.0, 5.0, "this line is way too long")])
    assert all(issue.severity == "error" for issue in issues)


def test_auto_fix_removes_empty_cues_and_reindexes():
    validator = _validator()
    cues = [SubtitleCue(0.0, 1.0, "   "), SubtitleCue(1.0, 2.0, "ok")]
    fixed = validator.auto_fix(cues)
    assert len(fixed) == 1
    assert fixed[0].index == 1


def test_auto_fix_corrects_overlap():
    validator = _validator()
    cues = [SubtitleCue(0.0, 2.0, "a"), SubtitleCue(1.5, 3.0, "b")]
    fixed = validator.auto_fix(cues)
    assert fixed[1].start >= fixed[0].end


def test_auto_fix_strips_blank_lines():
    validator = _validator()
    fixed = validator.auto_fix([SubtitleCue(0.0, 2.0, "first\n\nsecond")])
    assert fixed[0].text == "first\nsecond"


def test_warnings_method_only_warnings():
    validator = _validator(max_chars_per_line=10)
    cues = [SubtitleCue(0.0, 5.0, "very long line here")]
    assert all(issue.severity == "warning" for issue in validator.warnings(cues))
