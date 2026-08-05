"""Shared test fixtures.

- Qt runs offscreen (no display server needed).
- ``ffmpeg`` fixture wraps the resolved FFmpeg binary (imageio-ffmpeg).
- ``sample_video`` / ``sample_video_no_audio`` are tiny real videos created
  once per session with ffmpeg's lavfi sources; ``corrupt_video`` is a
  fake file used to exercise error paths.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from PySide6.QtWidgets import QApplication


def _make_video(ffmpeg, out_path: Path, *, duration: float, with_audio: bool) -> None:
    """Generate a tiny lavfi test video (video-only or with a sine tone)."""
    cmd = ["-y", "-f", "lavfi", "-i", f"testsrc2=duration={duration}:size=320x240:rate=30"]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=1"]
    cmd += ["-shortest"] if with_audio else []

    # Prefer libx264; fall back to mpeg4 for builds without x264.
    for vcodec in ("libx264", "mpeg4"):
        args = list(cmd) + ["-c:v", vcodec]
        if vcodec == "libx264":
            args += ["-pix_fmt", "yuv420p"]
        else:
            args += ["-q:v", "5"]
        if with_audio:
            args += ["-c:a", "aac"]
        args += [str(out_path)]
        rc, _, err = ffmpeg.run(args)
        if rc == 0 and out_path.exists() and out_path.stat().st_size > 0:
            return
    pytest.fail(f"Could not generate test video: {err[-500:]}")


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication (offscreen)."""
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(scope="session")
def ffmpeg():
    """FFmpegManager for the resolved binary (skips suite when missing)."""
    from src.video import FFmpegManager

    manager = FFmpegManager()
    if not manager.available():
        pytest.skip("ffmpeg binary not available; run `pip install imageio-ffmpeg`")
    return manager


@pytest.fixture(scope="session")
def media_dir(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("media")


@pytest.fixture(scope="session")
def sample_video(ffmpeg, media_dir) -> Path:
    out = media_dir / "sample.mp4"
    if not out.exists():
        _make_video(ffmpeg, out, duration=1.2, with_audio=True)
    return out


@pytest.fixture(scope="session")
def sample_video_no_audio(ffmpeg, media_dir) -> Path:
    out = media_dir / "sample_noaudio.mp4"
    if not out.exists():
        _make_video(ffmpeg, out, duration=0.8, with_audio=False)
    return out


@pytest.fixture(scope="session")
def corrupt_video(media_dir) -> Path:
    out = media_dir / "corrupt.mp4"
    out.write_bytes(b"this is definitely not a video file")
    return out


@pytest.fixture
def file_manager(tmp_path):
    """FileManager rooted in a per-test temp directory."""
    from src.video import FileManager

    return FileManager(temp_dir=tmp_path)


@pytest.fixture
def config(tmp_path):
    """ConfigManager writing to a temp directory (isolated per test)."""
    from src.core.config_manager import ConfigManager

    return ConfigManager(path=tmp_path / "settings.json")


@pytest.fixture
def app_state(config):
    from src.core.app_state import AppState

    return AppState(config)


@pytest.fixture
def theme_service():
    from src.services.theme_service import ThemeService

    return ThemeService()


@pytest.fixture
def main_window(qapp, config, app_state, theme_service):
    """A fully-built main window, closed after the test."""
    from src.main_window import MainWindow

    window = MainWindow(config, app_state, theme_service)
    yield window
    window.close()
