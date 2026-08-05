"""Whisper speech-recognition engine (Phase 3).

Word-level timestamps only — no subtitles, no rendering. The heavy lifting
runs through a small engine interface so tests use a fake engine and the
app uses faster-whisper.
"""

from __future__ import annotations

from .exceptions import (
    CorruptModelError,
    CUDAUnavailableError,
    EmptyAudioError,
    ModelDownloadError,
    ModelNotFoundError,
    OutOfMemoryError,
    TranscriptionCancelledError,
    TranscriptionError,
    UnsupportedLanguageError,
    WhisperError,
)
from .result import Segment, TranscriptResult, Word
from .settings import ComputeType, DeviceType, LanguageMode, WhisperSettings

__all__ = [
    "ComputeType",
    "CorruptModelError",
    "CUDAUnavailableError",
    "DeviceType",
    "EmptyAudioError",
    "LanguageMode",
    "ModelDownloadError",
    "ModelNotFoundError",
    "OutOfMemoryError",
    "Segment",
    "TranscriptResult",
    "TranscriptionCancelledError",
    "TranscriptionError",
    "UnsupportedLanguageError",
    "WhisperError",
    "WhisperSettings",
    "Word",
]
