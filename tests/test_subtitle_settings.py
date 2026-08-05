"""SubtitleSettings: defaults, config round-trip, validation."""

import pytest

from src.subtitles.settings import SubtitleSettings


def test_defaults():
    settings = SubtitleSettings()
    assert settings.default_format == "srt"
    assert settings.auto_generate is True
    assert settings.max_chars_per_line == 42
    assert settings.max_lines == 2
    assert settings.reading_speed_cps == 21.0
    assert settings.timing_optimization is True
    assert settings.validation_strictness == "balanced"


def test_from_config_missing_uses_defaults(config):
    settings = SubtitleSettings.from_config(config)
    assert settings.default_format == "srt"
    assert settings.max_lines == 2


def test_from_config_reads_values(config):
    config.set(
        "subtitles",
        {"default_format": "ass", "max_chars_per_line": 35, "max_lines": 3,
         "reading_speed_cps": 18.0, "validation_strictness": "strict",
         "auto_generate": False},
    )
    settings = SubtitleSettings.from_config(config)
    assert settings.default_format == "ass"
    assert settings.max_chars_per_line == 35
    assert settings.max_lines == 3
    assert settings.reading_speed_cps == 18.0
    assert settings.validation_strictness == "strict"
    assert settings.auto_generate is False


def test_to_dict_and_save_to_config(config):
    settings = SubtitleSettings(default_format="vtt", auto_generate=False)
    data = settings.to_dict()
    assert data["default_format"] == "vtt"
    assert data["auto_generate"] is False
    settings.save_to_config(config)
    assert config.get("subtitles")["default_format"] == "vtt"
    assert SubtitleSettings.from_config(config) == settings


def test_validate_unknown_format():
    with pytest.raises(ValueError, match="Unknown subtitle format"):
        SubtitleSettings(default_format="nope").validate()


def test_validate_chars_range():
    with pytest.raises(ValueError, match="max_chars_per_line"):
        SubtitleSettings(max_chars_per_line=5).validate()
    with pytest.raises(ValueError, match="max_chars_per_line"):
        SubtitleSettings(max_chars_per_line=500).validate()
    SubtitleSettings(max_chars_per_line=20).validate()


def test_validate_lines_range():
    with pytest.raises(ValueError, match="max_lines"):
        SubtitleSettings(max_lines=0).validate()
    SubtitleSettings(max_lines=3).validate()


def test_validate_reading_speed_range():
    with pytest.raises(ValueError, match="reading_speed_cps"):
        SubtitleSettings(reading_speed_cps=1.0).validate()
    SubtitleSettings(reading_speed_cps=15.0).validate()


def test_validate_durations():
    with pytest.raises(ValueError, match="min_display_duration"):
        SubtitleSettings(min_display_duration=0.0).validate()
    with pytest.raises(ValueError, match="max_display_duration"):
        SubtitleSettings(min_display_duration=5.0, max_display_duration=4.0).validate()


def test_validate_strictness():
    with pytest.raises(ValueError, match="validation_strictness"):
        SubtitleSettings(validation_strictness="extreme").validate()
    for level in ("lenient", "balanced", "strict"):
        SubtitleSettings(validation_strictness=level).validate()


def test_with_defaults_filled():
    settings = SubtitleSettings(max_chars_per_line=30)
    changed = settings.with_defaults_filled(max_lines=3)
    assert changed.max_chars_per_line == 30
    assert changed.max_lines == 3
    assert settings.max_lines == 2  # original untouched
