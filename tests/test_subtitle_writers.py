"""Subtitle writers: SRT / ASS / VTT / JSON / TXT + time formatters."""

import json

import pytest

from src.subtitles.ass_writer import ASSWriter
from src.subtitles.formatter import format_ass_time, format_srt_time, format_vtt_time
from src.subtitles.json_writer import JSONWriter
from src.subtitles.model import SubtitleCue, SubtitleDocument
from src.subtitles.srt_writer import SRTWriter
from src.subtitles.txt_writer import TXTWriter
from src.subtitles.vtt_writer import VTTWriter


def _doc(*cues: SubtitleCue) -> SubtitleDocument:
    return SubtitleDocument(cues=list(cues), language="en")


# --------------------------------------------------------------- formatters
def test_srt_time_formatting():
    assert format_srt_time(0.5) == "00:00:00,500"
    assert format_srt_time(65.25) == "00:01:05,250"
    assert format_srt_time(3725.0) == "01:02:05,000"


def test_vtt_time_formatting():
    assert format_vtt_time(0.5) == "00:00:00.500"
    assert format_vtt_time(65.25) == "00:01:05.250"


def test_ass_time_formatting():
    assert format_ass_time(0.5) == "0:00:00.50"
    assert format_ass_time(65.25) == "0:01:05.25"
    assert format_ass_time(3725.0) == "1:02:05.00"


# -------------------------------------------------------------------- SRT
def test_srt_basic():
    doc = _doc(SubtitleCue(0.5, 2.5, "Hello world", index=1))
    text = SRTWriter().write(doc)
    assert "1\n00:00:00,500 --> 00:00:02,500\nHello world" in text


def test_srt_multiple_cues_separated_by_blank_line():
    doc = _doc(
        SubtitleCue(0.0, 1.0, "First", index=1),
        SubtitleCue(1.5, 2.5, "Second", index=2),
    )
    text = SRTWriter().write(doc)
    assert "First\n\n2\n00:00:01,500 --> 00:00:02,500\nSecond" in text


def test_srt_preserves_multiline_text():
    doc = _doc(SubtitleCue(0.0, 2.0, "line one\nline two", index=1))
    assert "line one\nline two" in SRTWriter().write(doc)


def test_srt_empty_document():
    assert SRTWriter().write(_doc()) == ""


def test_srt_rtl_text_passes_through():
    doc = _doc(SubtitleCue(0.0, 1.0, "مرحبا بالعالم", index=1))
    assert "مرحبا بالعالم" in SRTWriter().write(doc)


# -------------------------------------------------------------------- ASS
def test_ass_header_blocks():
    text = ASSWriter().write(_doc())
    assert "[Script Info]" in text
    assert "[V4+ Styles]" in text
    assert "[Events]" in text


def test_ass_dialogue_line():
    doc = _doc(SubtitleCue(0.5, 2.5, "Hello world", index=1))
    text = ASSWriter().write(doc)
    assert "Dialogue: 0,0:00:00.50,0:00:02.50,Default,,0,0,0,,Hello world" in text


def test_ass_multiline_uses_backslash_n():
    doc = _doc(SubtitleCue(0.0, 1.0, "line one\nline two", index=1))
    assert "line one\\Nline two" in ASSWriter().write(doc)


def test_ass_style_defined():
    assert "Style: Default,Arial," in ASSWriter().write(_doc())


def test_ass_escapes_override_tags():
    doc = _doc(SubtitleCue(0.0, 1.0, "use {bold} braces", index=1))
    text = ASSWriter().write(doc)
    assert "\\{bold\\}" in text
    assert "{bold}" not in text


# -------------------------------------------------------------------- VTT
def test_vtt_starts_with_webvtt():
    assert VTTWriter().write(_doc(SubtitleCue(0.0, 1.0, "hi"))) == "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhi\n"


def test_vtt_time_format():
    doc = _doc(SubtitleCue(1.0, 2.5, "hi", index=1))
    assert "00:00:01.000 --> 00:00:02.500" in VTTWriter().write(doc)


def test_vtt_empty_document():
    assert VTTWriter().write(_doc()) == "WEBVTT\n"


# -------------------------------------------------------------------- JSON
def test_json_structure():
    doc = _doc(SubtitleCue(0.0, 2.5, "Hello", index=1))
    data = json.loads(JSONWriter().write(doc))
    assert data["format"] == "autocaption-studio/subtitles"
    assert data["cues"][0]["text"] == "Hello"
    assert data["cues"][0]["start"] == 0.0


def test_json_empty_document():
    data = json.loads(JSONWriter().write(_doc()))
    assert data["cues"] == []


def test_json_roundtrip():
    doc = _doc(SubtitleCue(0.0, 1.0, "Hello", index=1))
    data = json.loads(JSONWriter().write(doc))
    assert SubtitleDocument.from_dict(data).cues == doc.cues


# -------------------------------------------------------------------- TXT
def test_txt_writer():
    doc = _doc(SubtitleCue(0.0, 1.0, "First", index=1), SubtitleCue(2.0, 3.0, "Second", index=2))
    assert TXTWriter().write(doc) == "First\n\nSecond\n"


def test_txt_skips_empty_cues():
    doc = _doc(SubtitleCue(0.0, 1.0, "", index=1), SubtitleCue(2.0, 3.0, "Real", index=2))
    assert TXTWriter().write(doc) == "Real\n"


# --------------------------------------------------------- plugin contract
@pytest.mark.parametrize(
    "writer, ext",
    [(SRTWriter(), "srt"), (ASSWriter(), "ass"), (VTTWriter(), "vtt"), (JSONWriter(), "json"), (TXTWriter(), "txt")],
)
def test_writers_expose_plugin_metadata(writer, ext):
    assert writer.extension == ext
    assert writer.name
    assert callable(writer.write)
