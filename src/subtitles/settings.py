"""Subtitle settings (persisted under ``config/settings.json -> subtitles``)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from ..core.constants import SUBTITLE_FORMATS

VALID_STRICTNESS = ("lenient", "balanced", "strict")


@dataclass
class SubtitleSettings:
    """All knobs for subtitle generation and export."""

    default_format: str = "srt"
    auto_generate: bool = True
    # -- line breaking -----------------------------------------------------
    max_chars_per_line: int = 42
    max_lines: int = 2
    reading_speed_cps: float = 21.0
    keep_phrases: bool = True
    break_at_punctuation: bool = True
    break_at_conjunctions: bool = True
    # -- timing ------------------------------------------------------------
    timing_optimization: bool = True
    min_display_duration: float = 0.8
    max_display_duration: float = 7.0
    min_gap: float = 0.05
    # -- punctuation -------------------------------------------------------
    auto_punctuation: bool = True
    capitalize_sentences: bool = True
    expand_contractions: bool = False
    remove_fillers: bool = False
    # -- validation --------------------------------------------------------
    validation_strictness: str = "balanced"

    # -- config integration ---------------------------------------------------
    @classmethod
    def from_config(cls, config: Any) -> "SubtitleSettings":
        raw = config.get("subtitles", {}) if hasattr(config, "get") else {}
        if not isinstance(raw, dict):
            raw = {}
        return cls(
            default_format=str(raw.get("default_format", "srt")),
            auto_generate=bool(raw.get("auto_generate", True)),
            max_chars_per_line=int(raw.get("max_chars_per_line", 42)),
            max_lines=int(raw.get("max_lines", 2)),
            reading_speed_cps=float(raw.get("reading_speed_cps", 21.0)),
            keep_phrases=bool(raw.get("keep_phrases", True)),
            break_at_punctuation=bool(raw.get("break_at_punctuation", True)),
            break_at_conjunctions=bool(raw.get("break_at_conjunctions", True)),
            timing_optimization=bool(raw.get("timing_optimization", True)),
            min_display_duration=float(raw.get("min_display_duration", 0.8)),
            max_display_duration=float(raw.get("max_display_duration", 7.0)),
            min_gap=float(raw.get("min_gap", 0.05)),
            auto_punctuation=bool(raw.get("auto_punctuation", True)),
            capitalize_sentences=bool(raw.get("capitalize_sentences", True)),
            expand_contractions=bool(raw.get("expand_contractions", False)),
            remove_fillers=bool(raw.get("remove_fillers", False)),
            validation_strictness=str(raw.get("validation_strictness", "balanced")),
        )

    def to_dict(self) -> dict:
        return {
            "default_format": self.default_format,
            "auto_generate": self.auto_generate,
            "max_chars_per_line": self.max_chars_per_line,
            "max_lines": self.max_lines,
            "reading_speed_cps": self.reading_speed_cps,
            "keep_phrases": self.keep_phrases,
            "break_at_punctuation": self.break_at_punctuation,
            "break_at_conjunctions": self.break_at_conjunctions,
            "timing_optimization": self.timing_optimization,
            "min_display_duration": self.min_display_duration,
            "max_display_duration": self.max_display_duration,
            "min_gap": self.min_gap,
            "auto_punctuation": self.auto_punctuation,
            "capitalize_sentences": self.capitalize_sentences,
            "expand_contractions": self.expand_contractions,
            "remove_fillers": self.remove_fillers,
            "validation_strictness": self.validation_strictness,
        }

    def save_to_config(self, config: Any) -> None:
        config.set("subtitles", self.to_dict())

    # -- validation -------------------------------------------------------------
    def validate(self) -> None:
        if self.default_format not in SUBTITLE_FORMATS:
            raise ValueError(f"Unknown subtitle format {self.default_format!r}")
        if not 10 <= self.max_chars_per_line <= 200:
            raise ValueError("max_chars_per_line must be between 10 and 200")
        if not 1 <= self.max_lines <= 4:
            raise ValueError("max_lines must be between 1 and 4")
        if not 5.0 <= self.reading_speed_cps <= 60.0:
            raise ValueError("reading_speed_cps must be between 5 and 60")
        if self.min_display_duration <= 0:
            raise ValueError("min_display_duration must be positive")
        if self.max_display_duration <= self.min_display_duration:
            raise ValueError("max_display_duration must exceed min_display_duration")
        if self.validation_strictness not in VALID_STRICTNESS:
            raise ValueError(f"validation_strictness must be one of {VALID_STRICTNESS}")

    def with_defaults_filled(self, **overrides: Any) -> "SubtitleSettings":
        return replace(self, **overrides)
