"""Transcript data model.

The JSON shape produced here is the contract for later phases (karaoke
highlighting consumes ``segments[].words[]``). Example::

    {
      "language": "en",
      "language_probability": 0.98,
      "duration": 132.4,
      "segments": [
        {"start": 0.00, "end": 2.31, "text": "Hello everyone.",
         "words": [{"word": "Hello", "start": 0.00, "end": 0.41, "probability": 0.98}]}
      ]
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass
class Word:
    """A single word with timestamps and confidence."""

    word: str
    start: float
    end: float
    probability: float = 1.0

    def to_dict(self) -> dict:
        return {
            "word": self.word,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "probability": round(self.probability, 3),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Word":
        return cls(
            word=str(data.get("word", "")),
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            probability=float(data.get("probability", 1.0)),
        )


@dataclass
class Segment:
    """A transcribed sentence/segment with optional word timestamps."""

    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "text": self.text,
            "words": [word.to_dict() for word in self.words],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Segment":
        return cls(
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            text=str(data.get("text", "")),
            words=[Word.from_dict(w) for w in data.get("words", []) if isinstance(w, dict)],
        )


@dataclass
class TranscriptResult:
    """Full transcription of one audio file."""

    language: str = "en"
    language_probability: float = 1.0
    duration: float = 0.0
    segments: list[Segment] = field(default_factory=list)

    # -- helpers ---------------------------------------------------------------
    def word_count(self) -> int:
        return sum(len(segment.words) for segment in self.segments)

    def full_text(self) -> str:
        """Plain text of the transcript (one line per segment)."""
        return "\n".join(segment.text.strip() for segment in self.segments if segment.text.strip())

    # -- serialization -----------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "language_probability": round(self.language_probability, 3),
            "duration": round(self.duration, 3),
            "segments": [segment.to_dict() for segment in self.segments],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_txt(self) -> str:
        """Plain-text rendering for ``output/transcripts/<video>.txt``."""
        return self.full_text()

    @classmethod
    def from_dict(cls, data: dict) -> "TranscriptResult":
        return cls(
            language=str(data.get("language", "en")),
            language_probability=float(data.get("language_probability", 1.0)),
            duration=float(data.get("duration", 0.0)),
            segments=[Segment.from_dict(s) for s in data.get("segments", []) if isinstance(s, dict)],
        )

    @classmethod
    def from_json(cls, text: str) -> "TranscriptResult":
        return cls.from_dict(json.loads(text))
