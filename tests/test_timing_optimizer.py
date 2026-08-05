"""Timing optimization: merge, split, gaps, overlaps."""

import pytest

from src.subtitles.model import SubtitleCue
from src.subtitles.timing_optimizer import TimingOptimizer


def _opt(**kwargs) -> TimingOptimizer:
    defaults = dict(min_display_duration=0.8, max_display_duration=7.0, min_gap=0.05)
    defaults.update(kwargs)
    return TimingOptimizer(**defaults)


def test_unchanged_when_timing_is_fine():
    opt = _opt()
    cues = [SubtitleCue(0.0, 2.0, "hello"), SubtitleCue(2.1, 4.0, "world")]
    result = opt.optimize(cues)
    assert len(result) == 2
    assert result[0].start == 0.0
    assert result[0].end == 2.0


def test_merges_short_cue_into_previous():
    opt = _opt()
    cues = [
        SubtitleCue(0.0, 2.0, "long caption"),
        SubtitleCue(2.05, 2.3, "tiny"),  # 0.25s < 0.8s
    ]
    result = opt.optimize(cues)
    assert len(result) == 1
    assert "long caption tiny" in result[0].text
    assert result[0].end >= 2.3


def test_extends_leading_short_cue():
    opt = _opt()
    cues = [
        SubtitleCue(0.0, 0.3, "quick"),  # too short, nothing before it
        SubtitleCue(1.0, 3.0, "next caption"),
    ]
    result = opt.optimize(cues)
    assert result[0].duration >= 0.8 - 1e-6
    assert result[0].end <= result[1].start - opt.min_gap + 1e-6


def test_splits_long_multiline_cue():
    opt = _opt(max_display_duration=7.0)
    cues = [SubtitleCue(0.0, 8.0, "alpha line\nbeta line")]
    result = opt.optimize(cues)
    assert len(result) == 2
    assert result[0].text == "alpha line"
    assert result[1].text == "beta line"
    assert result[0].duration <= 7.0 + 1e-6


def test_splits_long_single_line_cue():
    opt = _opt(max_display_duration=7.0, min_gap=0.0)
    cues = [SubtitleCue(0.0, 8.0, "aaaa bbbb cccc dddd")]
    result = opt.optimize(cues)
    assert len(result) == 2
    assert result[0].text == "aaaa bbbb"
    assert result[1].text == "cccc dddd"
    assert result[0].end == pytest.approx(result[1].start)


def test_does_not_split_single_word_long_cue():
    opt = _opt(max_display_duration=7.0)
    cues = [SubtitleCue(0.0, 8.0, "supercalifragilistic")]
    result = opt.optimize(cues)
    assert len(result) == 1


def test_inserts_minimum_gap():
    opt = _opt(min_gap=0.1)
    cues = [SubtitleCue(0.0, 1.0, "a"), SubtitleCue(1.02, 2.0, "b")]
    result = opt.optimize(cues)
    assert result[1].start >= 1.1 - 1e-6


def test_corrects_overlap():
    opt = _opt(min_gap=0.05)
    cues = [SubtitleCue(0.0, 2.0, "a"), SubtitleCue(1.5, 3.0, "b")]
    result = opt.optimize(cues)
    assert result[1].start >= result[0].end + opt.min_gap - 1e-6


def test_disabled_returns_cues_untouched():
    opt = _opt(enabled=False)
    cues = [SubtitleCue(0.0, 0.2, "tiny"), SubtitleCue(0.3, 5.0, "long")]
    result = opt.optimize(cues)
    assert len(result) == 2
    assert result[0].end == 0.2


def test_extends_dense_cue_for_reading_speed():
    opt = _opt(reading_speed_cps=10.0, min_gap=0.0)
    cues = [SubtitleCue(0.0, 1.0, "x" * 30)]  # 30 cps > 10
    result = opt.optimize(cues)
    assert result[0].duration >= 3.0 - 1e-6  # 30 chars at 10 cps needs 3s


def test_reading_speed_extension_respects_next_cue():
    opt = _opt(reading_speed_cps=10.0, min_gap=0.05)
    cues = [SubtitleCue(0.0, 1.0, "x" * 30), SubtitleCue(2.0, 4.0, "next caption")]
    result = opt.optimize(cues)
    assert result[0].end <= result[1].start - opt.min_gap + 1e-6
    assert result[0].duration < 3.0  # clipped by the next cue's start


def test_comfortable_cue_is_not_extended():
    opt = _opt(reading_speed_cps=21.0)
    cues = [SubtitleCue(0.0, 2.0, "a comfortably paced caption")]  # ~14 cps
    result = opt.optimize(cues)
    assert result[0].end == 2.0


def test_split_cues_only_carry_matching_words():
    opt = _opt(max_display_duration=7.0, min_gap=0.0)
    cue = SubtitleCue(
        0.0,
        8.0,
        "alpha line\nbeta line",
        words=[
            {"word": "alpha", "start": 0.0, "end": 1.0},
            {"word": "beta", "start": 7.0, "end": 8.0},
        ],
    )
    result = opt.optimize([cue])
    assert len(result) == 2
    assert [w["word"] for w in result[0].words] == ["alpha"]
    assert [w["word"] for w in result[1].words] == ["beta"]


def test_empty_input():
    assert _opt().optimize([]) == []


def test_results_are_reindexed():
    opt = _opt()
    cues = [SubtitleCue(0.0, 0.2, "x"), SubtitleCue(1.0, 3.0, "y")]
    result = opt.optimize(cues)
    assert [c.index for c in result] == list(range(1, len(result) + 1))
