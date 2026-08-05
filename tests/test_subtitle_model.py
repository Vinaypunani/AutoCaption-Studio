"""Subtitle model: cues, documents, transcript conversion."""

import pytest

from src.ai.whisper.result import Segment, TranscriptResult
from src.subtitles.exceptions import InvalidCueError
from src.subtitles.model import (
    SubtitleCue,
    SubtitleDocument,
    cues_from_transcript,
    merge_text,
    reindex,
)


def test_cue_defaults():
    cue = SubtitleCue(0.0, 2.5)
    assert cue.text == ""
    assert cue.index == 0
    assert cue.duration == 2.5
    assert cue.is_empty()


def test_cue_negative_duration_raises():
    with pytest.raises(InvalidCueError):
        SubtitleCue(3.0, 1.0)


def test_cue_line_count():
    assert SubtitleCue(0, 1, "one line").line_count == 1
    assert SubtitleCue(0, 1, "one\ntwo").line_count == 2
    assert SubtitleCue(0, 1).line_count == 0


def test_cue_roundtrip():
    cue = SubtitleCue(0.5, 2.5, "Hello world", index=3, words=[{"word": "Hello"}])
    restored = SubtitleCue.from_dict(cue.to_dict())
    assert restored == cue


def test_reindex_assigns_sequential_indexes():
    cues = [SubtitleCue(0, 1, "a", index=9), SubtitleCue(1, 2, "b", index=4)]
    fixed = reindex(cues)
    assert [c.index for c in fixed] == [1, 2]


def test_document_empty_and_count():
    doc = SubtitleDocument()
    assert doc.is_empty()
    assert doc.cue_count() == 0


def test_document_to_dict_roundtrip():
    doc = SubtitleDocument(
        cues=[SubtitleCue(0, 1, "hi", index=1)],
        language="en",
        duration=1.5,
    )
    restored = SubtitleDocument.from_dict(doc.to_dict())
    assert restored.cues == doc.cues
    assert restored.language == "en"
    assert restored.duration == 1.5


def test_document_from_transcript_metadata():
    transcript = TranscriptResult(language="es", duration=9.5)
    doc = SubtitleDocument.from_transcript(transcript)
    assert doc.language == "es"
    assert doc.duration == 9.5


def test_cues_from_transcript_skips_empty_segments():
    transcript = TranscriptResult(
        segments=[
            Segment(0.0, 1.0, "  "),  # empty — skipped
            Segment(1.0, 2.5, "Hello there", words=[]),
            Segment(2.5, 4.0, "Second line"),
        ]
    )
    cues = cues_from_transcript(transcript)
    assert len(cues) == 2
    assert cues[0].text == "Hello there"
    assert cues[0].start == 1.0
    # Indexes are position-based (empty segments are skipped but counted).
    assert cues[0].index == 2
    assert cues[1].index == 3


def test_cues_from_transcript_normalizes_whitespace():
    transcript = TranscriptResult(segments=[Segment(0, 1, "  spaced    out  ")])
    assert cues_from_transcript(transcript)[0].text == "spaced out"


def test_merge_text():
    assert merge_text("Hello", "world") == "Hello world"
    assert merge_text("", "world") == "world"
    assert merge_text("Hello", "") == "Hello"
