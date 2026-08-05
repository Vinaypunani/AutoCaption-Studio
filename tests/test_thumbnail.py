"""Thumbnail generation: real extraction, brightness logic, errors."""

from pathlib import Path

import pytest

from src.video.exceptions import ThumbnailGenerationError
from src.video.thumbnail import extract_frame, frame_brightness, generate_thumbnail


def test_generate_thumbnail_produces_image(ffmpeg, tmp_path, sample_video):
    out = generate_thumbnail(ffmpeg, sample_video, tmp_path, duration_sec=1.2)
    assert out.exists()
    assert out.stat().st_size > 0
    assert out.suffix == ".jpg"


def test_thumbnail_is_readable_image(ffmpeg, tmp_path, sample_video):
    out = generate_thumbnail(ffmpeg, sample_video, tmp_path, duration_sec=1.2)
    with out.open("rb") as handle:
        header = handle.read(2)
    assert header in (b"\xff\xd8",)  # JPEG magic


def test_frame_brightness_black_white(tmp_path):
    from PIL import Image

    black = tmp_path / "black.png"
    white = tmp_path / "white.png"
    Image.new("L", (64, 64), 0).save(black)
    Image.new("L", (64, 64), 255).save(white)

    assert frame_brightness(black) < 1.0
    assert frame_brightness(white) > 254.0


def test_frame_brightness_missing_file_returns_high():
    assert frame_brightness("C:/nope/missing.jpg") == 255.0


def test_thumbnail_skips_black_frames(ffmpeg, tmp_path, sample_video):
    """testsrc2 frames are colorful — the chosen frame must not be black."""
    out = generate_thumbnail(ffmpeg, sample_video, tmp_path, duration_sec=1.2)
    assert frame_brightness(out) >= 16.0


def test_extract_frame_at_offset(ffmpeg, tmp_path, sample_video):
    target = tmp_path / "frame.jpg"
    extract_frame(ffmpeg, sample_video, at_seconds=0.5, out_path=target)
    assert target.exists()
    assert target.stat().st_size > 0


def test_thumbnail_fails_on_corrupt_video(ffmpeg, tmp_path, corrupt_video):
    with pytest.raises(ThumbnailGenerationError):
        generate_thumbnail(ffmpeg, corrupt_video, tmp_path, duration_sec=1.0)


def test_thumbnail_fails_on_missing_video(ffmpeg, tmp_path):
    with pytest.raises(ThumbnailGenerationError):
        generate_thumbnail(ffmpeg, "C:/does/not/exist.mp4", tmp_path, duration_sec=1.0)
