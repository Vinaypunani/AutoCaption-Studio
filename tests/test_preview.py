"""PreviewPanel: construction and control states (no real playback)."""

import pytest

from src.video import preview as preview_module


def test_module_imports_and_multimedia_flag():
    # In the supported environment QtMultimedia should be importable.
    assert hasattr(preview_module, "QTMULTIMEDIA_AVAILABLE")


def test_preview_panel_builds(qapp):
    panel = preview_module.PreviewPanel()
    assert panel.play_button is not None
    assert panel.stop_button is not None
    assert panel.position_slider is not None
    assert not panel.has_source()


def test_preview_clear_disables_controls(qapp):
    panel = preview_module.PreviewPanel()
    panel.clear()
    assert not panel.has_source()
    assert not panel.play_button.isEnabled()
    assert not panel.stop_button.isEnabled()


def test_preview_set_source_existing_file(qapp, sample_video):
    panel = preview_module.PreviewPanel()
    panel.set_source(str(sample_video))
    assert panel.has_source()
    assert panel.play_button.isEnabled()


def test_preview_set_source_missing_file_does_not_crash(qapp):
    panel = preview_module.PreviewPanel()
    panel.set_source("C:/definitely/missing/video.mp4")  # async error, must not raise
    assert panel.has_source()


def test_playback_state_safe_without_source(qapp):
    panel = preview_module.PreviewPanel()
    panel.toggle_playback()  # no source -> no-op, must not raise
    assert not panel.is_playing()
