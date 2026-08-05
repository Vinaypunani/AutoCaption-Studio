"""Exception hierarchy for the video processing engine.

Every failure mode in Phase 2 maps to a typed exception so the UI and the
pipeline can react precisely (e.g. "missing audio track" vs "ffmpeg gone").
"""

from __future__ import annotations

from typing import Optional


class VideoProcessingError(Exception):
    """Base class for all video engine errors."""

    def __init__(self, message: str, *, details: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class FFmpegNotFoundError(VideoProcessingError):
    """No ffmpeg binary could be located."""


class FFmpegExecutionError(VideoProcessingError):
    """ffmpeg ran but exited with a non-zero code."""

    def __init__(self, command: list[str], stderr: str = "") -> None:
        tail = stderr.strip().splitlines()[-3:] if stderr.strip() else []
        message = f"FFmpeg failed: {'; '.join(tail) or command}"
        super().__init__(message, details=stderr)
        self.command = command


class UnsupportedFormatError(VideoProcessingError):
    """The file extension is not in the supported format list."""

    def __init__(self, path: str, supported: str) -> None:
        super().__init__(
            f"Unsupported video format: {path!r}. Supported formats: {supported}"
        )
        self.path = path


class VideoValidationError(VideoProcessingError):
    """The file failed validation (missing, unreadable, not a video)."""


class CorruptedVideoError(VideoValidationError):
    """The file exists but cannot be read as a video (corrupt / not media)."""


class MetadataExtractionError(VideoProcessingError):
    """Video metadata could not be extracted."""


class MissingCodecError(MetadataExtractionError):
    """The required codec is missing or unsupported by this ffmpeg build."""


class ThumbnailGenerationError(VideoProcessingError):
    """A thumbnail could not be generated."""


class AudioExtractionError(VideoProcessingError):
    """Audio extraction failed."""


class MissingAudioTrackError(AudioExtractionError):
    """The video has no audio stream to extract."""


class FileOperationError(VideoProcessingError):
    """Filesystem operation failed (permissions, I/O, naming)."""
