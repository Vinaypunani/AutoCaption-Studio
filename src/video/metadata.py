"""Video metadata extraction.

Prefers ``ffprobe -print_format json`` (accurate, structured); falls back to
parsing ``ffmpeg -i`` stderr when only an ffmpeg binary is available (e.g.
the one bundled with imageio-ffmpeg). Both paths converge on the
:class:`VideoMetadata` dataclass.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .exceptions import CorruptedVideoError, MetadataExtractionError
from .ffmpeg_manager import FFmpegManager

# ---------------------------------------------------------------------------
# Duration formatting
# ---------------------------------------------------------------------------
def format_duration(total_seconds: float | int) -> str:
    """Format seconds as ``H:MM:SS`` or ``MM:SS`` (or ``—`` for none)."""
    if not total_seconds or total_seconds <= 0:
        return "—"
    total = int(total_seconds)
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def format_bytes(size_bytes: int) -> str:
    """Format a byte count as a human-readable string."""
    if size_bytes <= 0:
        return "—"
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


def format_bitrate(bitrate: int) -> str:
    """Format a bitrate in bits/second (or ``—`` when unknown)."""
    if not bitrate or bitrate <= 0:
        return "—"
    return f"{bitrate / 1000:.0f} kbps"


def _gcd(width: int, height: int) -> int:
    return math.gcd(width or 1, height or 1)


def _aspect_ratio(width: int, height: int, dar: Optional[str] = None) -> str:
    """Return ``W:H`` — prefers the container's DAR, else reduced pixels."""
    if dar and ":" in dar:
        left, _, right = dar.partition(":")
        if left.isdigit() and right.isdigit() and int(right) > 0:
            return f"{int(left)}:{int(right)}"
    if width and height:
        divisor = _gcd(width, height)
        return f"{width // divisor}:{height // divisor}"
    return "—"


def _fraction_to_float(value: str | None) -> Optional[float]:
    if not value or value == "0/0":
        return None
    try:
        left, _, right = value.partition("/")
        if right and right.isdigit() and int(right) > 0:
            return float(left) / float(right)
        return float(value)
    except (ValueError, ZeroDivisionError):
        return None


@dataclass
class VideoMetadata:
    """Structured metadata for a single video file."""

    filename: str
    extension: str
    path: str
    duration_sec: float = 0.0
    width: int = 0
    height: int = 0
    aspect_ratio: str = "—"
    fps: float = 0.0
    video_codec: str = "—"
    bitrate: int = 0
    audio_codec: str = "—"
    audio_channels: int = 0
    file_size_bytes: int = 0
    creation_date: str = "—"

    # -- display helpers ----------------------------------------------------
    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}" if self.width and self.height else "—"

    @property
    def duration_display(self) -> str:
        return format_duration(self.duration_sec)

    @property
    def size_display(self) -> str:
        return format_bytes(self.file_size_bytes)

    @property
    def bitrate_display(self) -> str:
        return format_bitrate(self.bitrate)

    @property
    def channels_display(self) -> str:
        if self.audio_channels <= 0:
            return "—"
        names = {1: "Mono", 2: "Stereo"}
        return f"{self.audio_channels} ch ({names.get(self.audio_channels, 'multi')})"

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "extension": self.extension,
            "path": self.path,
            "duration_sec": self.duration_sec,
            "width": self.width,
            "height": self.height,
            "aspect_ratio": self.aspect_ratio,
            "fps": self.fps,
            "video_codec": self.video_codec,
            "bitrate": self.bitrate,
            "audio_codec": self.audio_codec,
            "audio_channels": self.audio_channels,
            "file_size_bytes": self.file_size_bytes,
            "creation_date": self.creation_date,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VideoMetadata":
        return cls(**data)


# ---------------------------------------------------------------------------
# Probing
# ---------------------------------------------------------------------------
def probe(path: str | Path, ffmpeg: FFmpegManager) -> VideoMetadata:
    """Extract :class:`VideoMetadata` for a video file.

    Raises :class:`CorruptedVideoError` when the file cannot be opened as a
    video and :class:`MetadataExtractionError` on other failures.
    """
    candidate = Path(path)
    if not candidate.exists():
        raise MetadataExtractionError(f"File not found: {candidate}")

    if ffmpeg.has_ffprobe():
        return _probe_with_ffprobe(candidate, ffmpeg)
    return _probe_with_ffmpeg_i(candidate, ffmpeg)


def _probe_with_ffprobe(path: Path, ffmpeg: FFmpegManager) -> VideoMetadata:
    returncode, stdout, stderr = ffmpeg.run_probe(
        ["-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    )
    if returncode != 0:
        detail = stderr.strip().splitlines()[-1] if stderr.strip() else "probe failed"
        raise CorruptedVideoError(f"Cannot read video: {detail}", details=stderr)
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise MetadataExtractionError(f"Invalid probe output for {path}") from exc
    return parse_ffprobe_json(data, path)


def _probe_with_ffmpeg_i(path: Path, ffmpeg: FFmpegManager) -> VideoMetadata:
    returncode, _, stderr = ffmpeg.run(["-hide_banner", "-i", str(path)])
    if "Input #0" not in stderr:
        detail = stderr.strip().splitlines()[-1] if stderr.strip() else "cannot open input"
        raise CorruptedVideoError(f"Cannot read video: {detail}", details=stderr)
    return parse_ffmpeg_i(stderr, path)


# ---------------------------------------------------------------------------
# Parsers (pure functions — unit-testable without ffmpeg)
# ---------------------------------------------------------------------------
def parse_ffprobe_json(data: dict, path: str | Path) -> VideoMetadata:
    """Build :class:`VideoMetadata` from an ffprobe JSON payload."""
    candidate = Path(path)
    fmt = data.get("format") or {}
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})

    tags = fmt.get("tags") or {}
    duration = float(fmt.get("duration") or video.get("duration") or 0.0)
    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    fps = _fraction_to_float(video.get("avg_frame_rate") or video.get("r_frame_rate"))

    return VideoMetadata(
        filename=candidate.name,
        extension=candidate.suffix.lower(),
        path=str(candidate),
        duration_sec=duration,
        width=width,
        height=height,
        aspect_ratio=_aspect_ratio(width, height, video.get("display_aspect_ratio")),
        fps=fps or 0.0,
        video_codec=video.get("codec_name") or "—",
        bitrate=int(video.get("bit_rate") or fmt.get("bit_rate") or 0),
        audio_codec=audio.get("codec_name") or "—",
        audio_channels=int(audio.get("channels") or 0),
        file_size_bytes=int(fmt.get("size") or 0) or (candidate.stat().st_size if candidate.exists() else 0),
        creation_date=str(tags.get("creation_time", "—")),
    )


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_BITRATE_RE = re.compile(r"bitrate:\s*(\d+)\s*kb/s")
_CREATION_RE = re.compile(r"creation_time\s*:\s*([^\s]+)")
_VIDEO_CODEc_RE = re.compile(r"Video:\s*([a-zA-Z0-9]+)")
_DIMS_RE = re.compile(r"(\d{2,5})x(\d{2,5})")
_FPS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*fps")
_DAR_RE = re.compile(r"DAR\s+(\d+):(\d+)")
_AUDIO_CODEC_RE = re.compile(r"Audio:\s*([a-zA-Z0-9]+)")
_CHANNELS_RE = re.compile(r"(?:\d+\s*Hz[^,]*,\s*)?(mono|stereo|5\.1(?:\(side\))?|7\.1|quad|2\.1)")


def parse_ffmpeg_i(stderr: str, path: str | Path) -> VideoMetadata:
    """Build :class:`VideoMetadata` by parsing ``ffmpeg -i`` stderr output."""
    candidate = Path(path)

    def _first(pattern: re.Pattern) -> Optional[re.Match]:
        return pattern.search(stderr)

    duration = 0.0
    match = _DURATION_RE.search(stderr)
    if match:
        hours, minutes, seconds = (float(g) for g in match.groups())
        duration = hours * 3600 + minutes * 60 + seconds

    bitrate = int(_BITRATE_RE.search(stderr).group(1)) * 1000 if _BITRATE_RE.search(stderr) else 0

    video_lines = [line for line in stderr.splitlines() if "Video:" in line]
    audio_lines = [line for line in stderr.splitlines() if "Audio:" in line]
    video_line = video_lines[0] if video_lines else ""
    audio_line = audio_lines[0] if audio_lines else ""

    video_codec = _VIDEO_CODEc_RE.search(video_line).group(1) if video_line else "—"
    audio_codec = _AUDIO_CODEC_RE.search(audio_line).group(1) if audio_line else "—"

    width = height = 0
    dims = _DIMS_RE.search(video_line)
    if dims:
        width, height = int(dims.group(1)), int(dims.group(2))

    fps = 0.0
    fps_match = _FPS_RE.search(video_line)
    if fps_match:
        fps = float(fps_match.group(1))

    channels = 0
    if audio_line:
        channels_match = _CHANNELS_RE.search(audio_line)
        if channels_match:
            label = channels_match.group(1).lower()
            if label == "mono":
                channels = 1
            elif label == "stereo":
                channels = 2
            else:
                channels = 2 if label.startswith("2.") else 6 if label.startswith("5.") else 8 if label.startswith("7.") else 2

    dar_match = _DAR_RE.search(video_line)
    dar = f"{dar_match.group(1)}:{dar_match.group(2)}" if dar_match else None

    creation = _CREATION_RE.search(stderr)
    return VideoMetadata(
        filename=candidate.name,
        extension=candidate.suffix.lower(),
        path=str(candidate),
        duration_sec=duration,
        width=width,
        height=height,
        aspect_ratio=_aspect_ratio(width, height, dar),
        fps=fps,
        video_codec=video_codec,
        bitrate=bitrate,
        audio_codec=audio_codec,
        audio_channels=channels,
        file_size_bytes=candidate.stat().st_size if candidate.exists() else 0,
        creation_date=creation.group(1) if creation else "—",
    )
