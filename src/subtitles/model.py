"""Subtitle data model — plain data, no logic beyond serialization.

A :class:`SubtitleCue` is one caption (a time range + one or more text lines).
A :class:`SubtitleDocument` is the ordered collection produced by the engine
and consumed by the writers and the preview generator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from ..ai.whisper.result import Segment, TranscriptResult
from .exceptions import InvalidCueError


@dataclass
class SubtitleCue:
    """One caption: a time range and its (possibly multi-line) text."""

    start: float
    end: float
    text: str = ""
    index: int = 0
    words: list[dict] = field(default_factory=list)  # from transcript (styling later)

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise InvalidCueError(
                f"Cue {self.index}: end ({self.end:g}s) before start ({self.start:g}s)"
            )

    # -- helpers ---------------------------------------------------------------
    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def line_count(self) -> int:
        return max(1, self.text.count("\n") + 1) if self.text else 0

    def is_empty(self) -> bool:
        return not self.text.strip()

    # -- serialization -----------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "text": self.text,
            "words": list(self.words),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SubtitleCue":
        return cls(
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            text=str(data.get("text", "")),
            index=int(data.get("index", 0)),
            words=list(data.get("words", []) or []),
        )


@dataclass
class SubtitleDocument:
    """Ordered caption collection plus optional metadata/validation notes."""

    cues: list[SubtitleCue] = field(default_factory=list)
    language: str = ""
    duration: float = 0.0
    validation_issues: list = field(default_factory=list)  # ValidationIssue

    # -- helpers ---------------------------------------------------------------
    def is_empty(self) -> bool:
        return not self.cues

    def cue_count(self) -> int:
        return len(self.cues)

    def to_dict(self) -> dict:
        return {
            "format": "autocaption-studio/subtitles",
            "version": 1,
            "language": self.language,
            "duration": round(self.duration, 3),
            "cues": [cue.to_dict() for cue in self.cues],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SubtitleDocument":
        return cls(
            cues=[SubtitleCue.from_dict(c) for c in data.get("cues", []) if isinstance(c, dict)],
            language=str(data.get("language", "")),
            duration=float(data.get("duration", 0.0)),
        )

    # -- construction -----------------------------------------------------------
    @classmethod
    def from_transcript(cls, transcript: TranscriptResult, cues: Optional[list[SubtitleCue]] = None) -> "SubtitleDocument":
        """Wrap transcript metadata; the engine fills in the cues."""
        return cls(
            cues=list(cues or []),
            language=transcript.language,
            duration=transcript.duration,
        )


def cues_from_transcript(transcript: TranscriptResult) -> list[SubtitleCue]:
    """Convert transcript segments to raw cues (no line breaking yet)."""
    cues: list[SubtitleCue] = []
    for i, segment in enumerate(transcript.segments):
        if not segment.text.strip():
            continue
        cues.append(
            SubtitleCue(
                start=segment.start,
                end=segment.end,
                text=" ".join(segment.text.split()),
                index=i + 1,
                words=[w.to_dict() for w in segment.words],
            )
        )
    return cues


def reindex(cues: Iterable[SubtitleCue]) -> list[SubtitleCue]:
    """Return cues with sequential ``index`` values (1-based)."""
    return [SubtitleCue(c.start, c.end, c.text, index=i + 1, words=c.words) for i, c in enumerate(cues)]


def merge_text(a: str, b: str) -> str:
    """Join two cue texts with a space, collapsing existing newlines safely."""
    if not a.strip():
        return b
    if not b.strip():
        return a
    return f"{a.rstrip()} {b.lstrip()}"
