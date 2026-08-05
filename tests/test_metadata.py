"""Video metadata: probing, pure parsers, error paths, formatters."""

import pytest

from src.video.exceptions import CorruptedVideoError, MetadataExtractionError
from src.video.metadata import (
    format_bitrate,
    format_bytes,
    format_duration,
    parse_ffmpeg_i,
    parse_ffprobe_json,
    probe,
)


def test_probe_real_video(ffmpeg, sample_video):
    meta = probe(sample_video, ffmpeg)
    assert meta.filename == "sample.mp4"
    assert meta.extension == ".mp4"
    assert 0.8 <= meta.duration_sec <= 1.8
    assert meta.width == 320
    assert meta.height == 240
    assert meta.aspect_ratio == "4:3"
    assert abs(meta.fps - 30) <= 6  # 30 fps, allow 29.97
    assert meta.video_codec in ("h264", "mpeg4")
    assert meta.audio_codec in ("aac", "mp3")
    assert meta.audio_channels in (1, 2)
    assert meta.file_size_bytes > 0
    assert meta.resolution == "320x240"
    assert ":" in meta.duration_display


def test_probe_missing_file(ffmpeg):
    with pytest.raises(MetadataExtractionError):
        probe("C:/does/not/exist.mp4", ffmpeg)


def test_probe_corrupt_file(ffmpeg, corrupt_video):
    with pytest.raises(CorruptedVideoError):
        probe(corrupt_video, ffmpeg)


def test_parse_ffmpeg_i_unit():
    stderr = """Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'clip.mp4':
  Metadata:
    creation_time   : 2024-01-01T00:00:00.000000Z
  Duration: 00:00:05.00, start: 0.000000, bitrate: 842 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(progressive), 1920x1080 [SAR 1:1 DAR 16:9], 30 fps, 30 tbr, 15360 tbn, 60 tbc (default)
  Stream #0:1[0x1](und): Audio: aac (LC) (mp4a / 0x6134706D), 44100 Hz, stereo, fltp, 128 kb/s (default)
"""
    meta = parse_ffmpeg_i(stderr, "C:/videos/clip.mp4")
    assert meta.filename == "clip.mp4"
    assert meta.extension == ".mp4"
    assert meta.duration_sec == pytest.approx(5.0)
    assert meta.width == 1920 and meta.height == 1080
    assert meta.aspect_ratio == "16:9"
    assert meta.fps == pytest.approx(30.0)
    assert meta.video_codec == "h264"
    assert meta.audio_codec == "aac"
    assert meta.audio_channels == 2
    assert meta.bitrate == 842_000
    assert meta.creation_date == "2024-01-01T00:00:00.000000Z"


def test_parse_ffprobe_json_unit():
    data = {
        "format": {
            "duration": "12.500000",
            "size": "1048576",
            "bit_rate": "671088",
            "tags": {"creation_time": "2023-06-15T10:00:00.000000Z"},
        },
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1280,
                "height": 720,
                "avg_frame_rate": "30000/1001",
                "display_aspect_ratio": "16:9",
                "bit_rate": "600000",
            },
            {"codec_type": "audio", "codec_name": "aac", "channels": 2},
        ],
    }
    meta = parse_ffprobe_json(data, "C:/videos/ffprobe.mp4")
    assert meta.duration_sec == pytest.approx(12.5)
    assert meta.fps == pytest.approx(30000 / 1001)
    assert meta.aspect_ratio == "16:9"
    assert meta.width == 1280 and meta.height == 720
    assert meta.video_codec == "h264"
    assert meta.audio_codec == "aac"
    assert meta.audio_channels == 2
    assert meta.file_size_bytes == 1_048_576


def test_formatters():
    assert format_duration(0) == "—"
    assert format_duration(65) == "01:05"
    assert format_duration(3725) == "1:02:05"
    assert format_bytes(0) == "—"
    assert format_bytes(2048) == "2.0 KB"
    assert format_bitrate(0) == "—"
    assert format_bitrate(128_000) == "128 kbps"
