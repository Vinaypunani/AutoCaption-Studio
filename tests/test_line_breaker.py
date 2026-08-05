"""Line breaking: char limits, break preferences, phrases, reading speed."""

import pytest

from src.subtitles.line_breaker import LineBreaker
from src.subtitles.model import SubtitleCue


def _breaker(**kwargs) -> LineBreaker:
    defaults = dict(max_chars_per_line=20, max_lines=2)
    defaults.update(kwargs)
    return LineBreaker(**defaults)


def test_short_text_stays_one_line():
    breaker = _breaker()
    assert breaker.break_text("Short caption") == ["Short caption"]


def test_breaks_at_word_boundary():
    breaker = _breaker(max_chars_per_line=20)
    lines = breaker.break_text("one two three four five six")
    assert lines == ["one two three four", "five six"]
    assert all(len(line) <= 20 for line in lines)


def test_breaks_after_punctuation_preferred():
    breaker = _breaker(max_chars_per_line=20)
    lines = breaker.break_text("Hello everyone, this is a test")
    assert lines == ["Hello everyone,", "this is a test"]


def test_breaks_before_conjunction():
    breaker = _breaker(max_chars_per_line=20)
    lines = breaker.break_text("I went to the store and bought milk")
    assert lines[0].endswith("store")
    assert lines[1].startswith("and")


def test_keeps_phrases_together():
    breaker = _breaker(max_chars_per_line=12, keep_phrases=True)
    lines = breaker.break_text("we need in order to finish")
    assert "in order to" in " ".join(lines)
    # The phrase-start word moves to the next line instead of dangling.
    assert "in" not in lines[0].split()[-1:]
    assert lines[0].split()[-1] == "need"


def test_phrase_keeping_disabled():
    breaker = _breaker(max_chars_per_line=12, keep_phrases=False)
    lines = breaker.break_text("we need in order to finish")
    assert lines[0].split()[-1] == "in"


def test_long_word_overflows_line():
    breaker = _breaker(max_chars_per_line=10)
    lines = breaker.break_text("short supercalifragilisticexpialidocious end")
    assert any("supercalifragilisticexpialidocious" in line for line in lines)


def test_break_cue_groups_lines_into_cues():
    breaker = _breaker(max_chars_per_line=12, max_lines=2)
    cue = SubtitleCue(0.0, 4.0, "alpha beta gamma delta epsilon zeta eta")
    result = breaker.break_cue(cue)
    assert len(result) > 1
    for sub in result:
        assert sub.line_count <= 2


def test_break_cue_distributes_time_proportionally():
    breaker = _breaker(max_chars_per_line=12, max_lines=2)
    cue = SubtitleCue(0.0, 4.0, "alpha beta gamma delta epsilon zeta eta")
    result = breaker.break_cue(cue)
    assert len(result) == 2
    total = sum(sub.duration for sub in result)
    assert total == pytest.approx(4.0)
    assert result[0].end == pytest.approx(result[1].start)
    # Chars per second stays roughly balanced across the split cues.
    cps = [len(sub.text) / sub.duration for sub in result]
    assert max(cps) - min(cps) < 2.0


def test_break_cue_single_group_keeps_full_time():
    breaker = _breaker(max_chars_per_line=60, max_lines=2)
    cue = SubtitleCue(1.0, 5.0, "alpha beta gamma")
    result = breaker.break_cue(cue)
    assert len(result) == 1
    assert result[0].start == 1.0
    assert result[0].end == 5.0


def test_break_cue_splits_assign_words_to_matching_cue():
    breaker = _breaker(max_chars_per_line=12, max_lines=1)
    cue = SubtitleCue(
        0.0,
        4.0,
        "alpha beta gamma delta",
        words=[
            {"word": "alpha", "start": 0.0, "end": 1.0},
            {"word": "beta", "start": 1.0, "end": 2.0},
            {"word": "gamma", "start": 2.0, "end": 3.0},
            {"word": "delta", "start": 3.0, "end": 4.0},
        ],
    )
    result = breaker.break_cue(cue)
    assert len(result) == 2
    first_words = [w["word"] for w in result[0].words]
    second_words = [w["word"] for w in result[1].words]
    assert "alpha" in first_words
    assert "delta" in second_words
    # A word whose timing lies outside a cue's range is not attached to it.
    assert all(w["end"] >= result[0].start for w in result[0].words)


def test_break_cue_handles_empty_text():
    breaker = _breaker()
    cue = SubtitleCue(0.0, 1.0, "   ")
    result = breaker.break_cue(cue)
    assert len(result) == 1
    assert result[0].is_empty()


def test_break_cue_without_duration_returns_single_cue():
    breaker = _breaker(max_chars_per_line=10, max_lines=2)
    cue = SubtitleCue(0.0, 0.0, "alpha beta gamma delta")
    result = breaker.break_cue(cue)
    assert len(result) == 1
    assert result[0].line_count <= 2
