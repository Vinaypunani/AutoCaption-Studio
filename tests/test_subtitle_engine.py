"""Subtitle engine: build pipeline, plugin registry, export."""

import pytest

from src.ai.whisper.result import Segment, TranscriptResult
from src.subtitles.exceptions import EmptySubtitleError, UnsupportedFormatError
from src.subtitles.model import SubtitleCue, SubtitleDocument
from src.subtitles.settings import SubtitleSettings
from src.subtitles.subtitle_engine import SubtitleEngine


def _transcript() -> TranscriptResult:
    return TranscriptResult(
        language="en",
        duration=6.0,
        segments=[
            Segment(0.0, 2.0, "Hello everyone, this is a great day."),
            Segment(2.5, 4.0, "We should celebrate together."),
            Segment(4.5, 6.0, "Thank you for watching."),
        ],
    )


def test_default_formats_available():
    engine = SubtitleEngine()
    assert set(engine.available_formats()) == {"srt", "ass", "vtt", "json", "txt"}


def test_build_produces_document():
    engine = SubtitleEngine()
    doc = engine.build(_transcript(), SubtitleSettings())
    assert doc.cue_count() >= 3
    assert doc.language == "en"
    assert not doc.is_empty()


def test_build_applies_punctuation_and_line_limits():
    engine = SubtitleEngine()
    doc = engine.build(_transcript(), SubtitleSettings(max_chars_per_line=30, max_lines=2))
    for cue in doc.cues:
        assert cue.line_count <= 2
        assert cue.text.strip().endswith((".", "!", "?", "…"))


def test_build_attaches_validation_issues():
    engine = SubtitleEngine()
    doc = engine.build(_transcript(), SubtitleSettings())
    assert hasattr(doc, "validation_issues")


def test_build_empty_transcript_raises():
    engine = SubtitleEngine()
    with pytest.raises(EmptySubtitleError):
        engine.build(TranscriptResult(segments=[Segment(0, 1, "   ")]), SubtitleSettings())


def test_export_each_format():
    engine = SubtitleEngine()
    doc = engine.build(_transcript(), SubtitleSettings())
    assert engine.export(doc, "srt").startswith("1\n")
    assert engine.export(doc, "vtt").startswith("WEBVTT")
    assert engine.export(doc, "ass").startswith("[Script Info]")
    assert engine.export(doc, "json").startswith("{")
    assert engine.export(doc, "txt").strip()


def test_export_all_covers_every_format():
    engine = SubtitleEngine()
    doc = engine.build(_transcript(), SubtitleSettings())
    contents = engine.export_all(doc)
    assert set(contents) == {"srt", "ass", "vtt", "json", "txt"}


def test_unsupported_format_raises():
    engine = SubtitleEngine()
    doc = engine.build(_transcript(), SubtitleSettings())
    with pytest.raises(UnsupportedFormatError, match="scc"):
        engine.export(doc, "scc")


def test_export_empty_document_raises():
    engine = SubtitleEngine()
    with pytest.raises(EmptySubtitleError):
        engine.export(SubtitleDocument(), "srt")


def test_custom_writer_plugin_registered_and_used():
    class SCCWriter:
        extension = "scc"
        name = "Scenarist Closed Captions"

        def write(self, document, options=None):
            return f"Scenarist_SCC V1.0\n{len(document.cues)} cues"

    engine = SubtitleEngine()
    engine.register_writer(SCCWriter())
    assert "scc" in engine.available_formats()
    doc = engine.build(_transcript(), SubtitleSettings())
    assert "Scenarist_SCC" in engine.export(doc, "scc")


def test_invalid_plugin_rejected():
    engine = SubtitleEngine()
    with pytest.raises(TypeError):
        engine.register_writer(object())  # type: ignore[arg-type]


def test_rtl_text_survives_full_pipeline():
    transcript = TranscriptResult(
        language="ar",
        segments=[Segment(0.0, 2.0, "مرحبا بالعالم هذا نص طويل")],
    )
    engine = SubtitleEngine()
    doc = engine.build(transcript, SubtitleSettings())
    srt = engine.export(doc, "srt")
    assert "مرحبا بالعالم" in srt


def test_build_distributes_segments_into_cues():
    engine = SubtitleEngine()
    doc = engine.build(_transcript(), SubtitleSettings())
    assert doc.duration == pytest.approx(6.0)
