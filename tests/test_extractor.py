"""Audio extraction: WAV output, progress reporting, error mapping."""

import pytest

from src.video.exceptions import AudioExtractionError, MissingAudioTrackError
from src.video.extractor import extract_audio


def test_extract_audio_produces_wav(ffmpeg, tmp_path, sample_video):
    out = extract_audio(ffmpeg, sample_video, tmp_path, duration_sec=1.2)
    assert out.exists()
    assert out.stat().st_size > 0
    assert out.suffix == ".wav"


def test_wav_has_riff_header(ffmpeg, tmp_path, sample_video):
    out = extract_audio(ffmpeg, sample_video, tmp_path, duration_sec=1.2)
    with out.open("rb") as handle:
        assert handle.read(4) == b"RIFF"


def test_extract_audio_reports_progress(ffmpeg, tmp_path, sample_video):
    calls: list[float] = []
    extract_audio(
        ffmpeg, sample_video, tmp_path,
        duration_sec=1.2, on_progress=calls.append,
    )
    assert calls, "progress callback never called"
    assert calls[-1] == 1.0


def test_missing_audio_track_raises(ffmpeg, tmp_path, sample_video_no_audio):
    with pytest.raises(MissingAudioTrackError):
        extract_audio(ffmpeg, sample_video_no_audio, tmp_path, duration_sec=0.8)


def test_missing_file_raises(ffmpeg, tmp_path):
    with pytest.raises(AudioExtractionError):
        extract_audio(ffmpeg, "C:/does/not/exist.mp4", tmp_path)


def test_extract_overwrites_existing_output(ffmpeg, tmp_path, sample_video):
    out = extract_audio(ffmpeg, sample_video, tmp_path, duration_sec=1.2)
    first_size = out.stat().st_size
    out.write_bytes(b"stale")
    again = extract_audio(ffmpeg, sample_video, tmp_path, duration_sec=1.2)
    assert again == out
    assert again.stat().st_size >= first_size
