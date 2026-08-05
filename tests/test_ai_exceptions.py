"""Exception hierarchy: every Whisper error is catchable as WhisperError."""

import pytest

from src.ai.whisper.exceptions import (
    CUDAUnavailableError,
    CorruptModelError,
    EmptyAudioError,
    ModelDownloadError,
    ModelNotFoundError,
    OutOfMemoryError,
    TranscriptionCancelledError,
    TranscriptionError,
    UnsupportedLanguageError,
    WhisperError,
)

_ALL = [
    ModelDownloadError,
    ModelNotFoundError,
    CorruptModelError,
    CUDAUnavailableError,
    OutOfMemoryError,
    UnsupportedLanguageError,
    EmptyAudioError,
    TranscriptionCancelledError,
    TranscriptionError,
]


@pytest.mark.parametrize("exc_type", _ALL)
def test_all_errors_are_whisper_errors(exc_type):
    assert issubclass(exc_type, WhisperError)


def test_each_error_carries_message():
    error = ModelDownloadError("failed to fetch")
    assert "failed to fetch" in str(error)


def test_except_whisper_error_catches_any():
    for exc_type in _ALL:
        with pytest.raises(WhisperError):
            raise exc_type("boom")


def test_errors_are_distinct_types():
    assert len({c for c in _ALL}) == len(_ALL)
