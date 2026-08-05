"""Transcript result model: words, segments, JSON/TXT serialization."""

import json

from src.ai.whisper.result import Segment, TranscriptResult, Word


def _result() -> TranscriptResult:
    return TranscriptResult(
        language="en",
        language_probability=0.98,
        duration=2.5,
        segments=[
            Segment(
                start=0.0,
                end=2.5,
                text="Hello everyone.",
                words=[
                    Word("Hello", 0.0, 0.41, 0.98),
                    Word("everyone.", 0.41, 1.3, 0.95),
                ],
            )
        ],
    )


def test_word_dict_roundtrip():
    word = Word("Hello", 0.0, 0.41, 0.98)
    data = word.to_dict()
    assert data == {"word": "Hello", "start": 0.0, "end": 0.41, "probability": 0.98}
    assert Word.from_dict(data) == word


def test_segment_dict_roundtrip():
    segment = Segment(1.0, 2.0, "text", [Word("a", 1.0, 1.2, 0.9)])
    assert Segment.from_dict(segment.to_dict()) == segment


def test_transcript_dict_roundtrip():
    result = _result()
    assert TranscriptResult.from_dict(result.to_dict()) == result


def test_transcript_to_json_and_back():
    result = _result()
    text = result.to_json()
    assert json.loads(text)["language"] == "en"
    assert TranscriptResult.from_json(text) == result


def test_full_text_joins_segments():
    result = TranscriptResult(
        segments=[
            Segment(0, 1, "Hello there."),
            Segment(1, 2, "How are you?"),
        ]
    )
    assert result.full_text() == "Hello there.\nHow are you?"


def test_to_txt_matches_full_text():
    result = _result()
    assert result.to_txt() == "Hello everyone."


def test_word_count_sums_words():
    result = _result()
    assert result.word_count() == 2
    assert TranscriptResult().word_count() == 0


def test_from_dict_ignores_garbage_segments_and_words():
    result = TranscriptResult.from_dict(
        {
            "language": "en",
            "segments": [
                {"start": 0, "end": 1, "text": "ok", "words": [{"word": "ok", "start": 0, "end": 0.2}]},
                "not-a-dict",
                {"start": 1, "end": 2, "text": "bad words", "words": ["garbage", {"word": "w", "start": 0, "end": 1}]},
            ],
        }
    )
    assert len(result.segments) == 2
    assert result.segments[1].words == [Word("w", 0, 1)]


def test_word_defaults():
    word = Word("plain", 0.0, 1.0)
    assert word.probability == 1.0
