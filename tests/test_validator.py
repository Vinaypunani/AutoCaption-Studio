"""Video validation: supported formats, file checks, corrupt rejection."""

import pytest

from src.video.exceptions import CorruptedVideoError, UnsupportedFormatError, VideoValidationError
from src.video.validator import (
    is_supported_extension,
    validate,
    validate_extension,
    validate_file,
    validate_playable,
)


def test_is_supported_extension_accepts_phase2_formats():
    for ext in (".mp4", ".MOV", ".avi", ".mkv", ".webm", ".M4V"):
        assert is_supported_extension(f"clip{ext}")


def test_is_supported_extension_rejects_others():
    for ext in (".txt", ".flv", ".wmv", ".mp3", ".png", ""):
        assert not is_supported_extension(f"clip{ext}")


def test_validate_extension_error_message():
    with pytest.raises(UnsupportedFormatError) as excinfo:
        validate_extension("C:/videos/clip.flv")
    assert "Unsupported" in str(excinfo.value)
    assert "mp4" in str(excinfo.value)  # supported list included in the message


def test_validate_file_missing():
    with pytest.raises(VideoValidationError):
        validate_file("C:/does/not/exist.mp4")


def test_validate_file_directory(tmp_path):
    directory = tmp_path / "videos.mp4"
    directory.mkdir()
    with pytest.raises(VideoValidationError):
        validate_file(directory)


def test_validate_playable_rejects_corrupt(ffmpeg, corrupt_video):
    with pytest.raises(CorruptedVideoError):
        validate_playable(corrupt_video, ffmpeg)


def test_validate_playable_accepts_real_video(ffmpeg, sample_video):
    validate_playable(sample_video, ffmpeg)  # must not raise


def test_validate_full_chain_ok(ffmpeg, sample_video):
    validate(sample_video, ffmpeg)  # must not raise


def test_validate_rejects_unsupported_extension(ffmpeg):
    with pytest.raises(UnsupportedFormatError):
        validate("C:/videos/clip.flv", ffmpeg)
