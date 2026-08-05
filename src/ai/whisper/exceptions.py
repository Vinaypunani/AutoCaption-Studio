"""Exception hierarchy for the Whisper engine (Phase 3)."""

from __future__ import annotations


class WhisperError(Exception):
    """Base class for all transcription errors."""


class ModelDownloadError(WhisperError):
    """A model download failed (network, disk, hub)."""


class ModelNotFoundError(WhisperError):
    """A model is not installed/cached and cannot be loaded."""


class CorruptModelError(WhisperError):
    """An installed model is incomplete or corrupt."""


class CUDAUnavailableError(WhisperError):
    """CUDA was requested but is not available on this machine."""


class OutOfMemoryError(WhisperError):
    """The model ran out of memory (lower compute type / smaller model)."""


class UnsupportedLanguageError(WhisperError):
    """A manually selected language is not supported by Whisper."""


class EmptyAudioError(WhisperError):
    """The audio contains no usable samples (silence/empty)."""


class TranscriptionCancelledError(WhisperError):
    """Transcription was cancelled by the user."""


class TranscriptionError(WhisperError):
    """Any other transcription failure."""
