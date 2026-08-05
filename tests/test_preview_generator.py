"""Subtitle preview generator (pure HTML)."""

from src.subtitles.model import SubtitleCue
from src.subtitles.preview_generator import render_cue_html, render_preview_html


def test_render_preview_contains_text():
    html = render_preview_html([SubtitleCue(0.0, 2.5, "Hello world", index=1)])
    assert "Hello world" in html
    assert "class=\"text\"" in html


def test_render_preview_shows_timestamps():
    html = render_preview_html([SubtitleCue(1.0, 2.5, "Hi", index=1)])
    assert "00:00:01,000" in html


def test_render_preview_hides_timestamps_when_disabled():
    html = render_preview_html([SubtitleCue(1.0, 2.5, "Hi", index=1)], show_timestamps=False)
    assert "00:00:01,000" not in html


def test_empty_cues_show_placeholder():
    assert "No subtitles to preview yet." in render_preview_html([])


def test_selected_cue_gets_highlight_class():
    html = render_preview_html(
        [SubtitleCue(0.0, 1.0, "a", index=1), SubtitleCue(1.0, 2.0, "b", index=2)],
        selected_index=2,
    )
    assert "cue selected" in html
    assert html.count("cue selected") == 1


def test_html_is_escaped():
    html = render_preview_html([SubtitleCue(0.0, 1.0, "<b>bold</b>", index=1)])
    assert "<b>bold</b>" not in html
    assert "&lt;b&gt;bold&lt;/b&gt;" in html


def test_multiline_cue_renders_break():
    html = render_cue_html(SubtitleCue(0.0, 1.0, "line one\nline two", index=1))
    assert "line one<br>line two" in html
