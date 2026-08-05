"""Video processing engine (Phase 2).

Pure-Python media operations (validation, metadata, thumbnails, audio
extraction) built exclusively on the centralized :mod:`ffmpeg_manager`
wrapper. No AI, transcription or subtitle generation here — that's Phase 3.
"""

from __future__ import annotations

from .exceptions import (
    AudioExtractionError,
    CorruptedVideoError,
    FFmpegExecutionError,
    FFmpegNotFoundError,
    FileOperationError,
    MetadataExtractionError,
    MissingAudioTrackError,
    MissingCodecError,
    ThumbnailGenerationError,
    UnsupportedFormatError,
    VideoProcessingError,
    VideoValidationError,
)
from .ffmpeg_manager import FFmpegManager
from .file_manager import FileManager
from .metadata import VideoMetadata, probe
from .thumbnail import generate_thumbnail

__all__ = [
    "AudioExtractionError",
    "CorruptedVideoError",
    "FFmpegExecutionError",
    "FFmpegNotFoundError",
    "FileOperationError",
    "FileManager",
    "FFmpegManager",
    "MetadataExtractionError",
    "MissingAudioTrackError",
    "MissingCodecError",
    "ThumbnailGenerationError",
    "UnsupportedFormatError",
    "VideoMetadata",
    "VideoProcessingError",
    "VideoValidationError",
    "generate_thumbnail",
    "probe",
]
