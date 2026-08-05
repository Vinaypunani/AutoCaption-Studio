"""FFmpegManager: binary discovery, execution, errors and progress."""

import pytest

from src.video.ffmpeg_manager import FFmpegManager
from src.video.exceptions import FFmpegExecutionError, FFmpegNotFoundError


def test_available_and_version(ffmpeg):
    assert ffmpeg.available() is True
    assert "ffmpeg" in ffmpeg.version().lower()


def test_run_captures_stdout(ffmpeg):
    returncode, stdout, _ = ffmpeg.run(["-version"])
    assert returncode == 0
    assert "ffmpeg" in stdout.lower()


def test_run_checked_raises_on_failure(ffmpeg):
    with pytest.raises(FFmpegExecutionError):
        ffmpeg.run_checked(["-i", "definitely_missing_file_xyz.mp4", "-f", "null", "-"])


def test_run_with_progress_reports_and_finishes(ffmpeg, tmp_path, sample_video):
    out = tmp_path / "progress.wav"
    calls: list[float] = []
    ffmpeg.run_with_progress(
        ["-y", "-i", str(sample_video), "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(out)],
        duration_sec=1.2,
        on_progress=calls.append,
    )
    assert out.exists()
    assert calls, "progress callback was never called"
    assert calls[-1] == 1.0


def test_explicit_binary_path_used(ffmpeg):
    manager = FFmpegManager(ffmpeg_path=ffmpeg.ffmpeg_binary())
    assert manager.available() is True
    assert manager.ffmpeg_binary() == ffmpeg.ffmpeg_binary()


def test_unavailable_binary_raises():
    manager = FFmpegManager(ffmpeg_path="C:/definitely/not/ffmpeg.exe")
    assert manager.available() is False
    with pytest.raises(FFmpegNotFoundError):
        manager.ffmpeg_binary()
    with pytest.raises(FFmpegNotFoundError):
        manager.run(["-version"])


def test_metadata_works_without_ffprobe_via_ffmpeg_fallback(ffmpeg, sample_video):
    """Forcing ffprobe off must still yield metadata via the ffmpeg -i parser."""
    from src.video.metadata import probe

    manager = FFmpegManager(ffmpeg_path=ffmpeg.ffmpeg_binary(), ffprobe_path="C:/definitely/not/ffprobe.exe")
    assert manager.available() is True
    assert manager.has_ffprobe() is False

    meta = probe(sample_video, manager)
    assert meta.width == 320
    assert meta.height == 240
    assert meta.duration_sec > 0
