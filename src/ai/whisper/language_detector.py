"""Language detection / selection for transcription.

Auto mode asks the engine to detect the spoken language; manual mode uses
the user's choice (validated against Whisper's supported codes).
"""

from __future__ import annotations

from typing import Any, Optional

from .exceptions import TranscriptionError, UnsupportedLanguageError
from .settings import LanguageMode, WhisperSettings


class LanguageDetector:
    """Resolves ``(language_code, probability)`` for a transcription run."""

    def __init__(self, engine: Optional[Any] = None) -> None:
        # ``engine`` is a TranscriptionEngine (duck-typed to avoid a cycle).
        self.engine = engine

    def resolve(self, audio: Any, settings: WhisperSettings) -> tuple[str, float]:
        """Return ``(language_code, probability)`` per the settings' mode."""
        settings.validate()
        if settings.language_mode is LanguageMode.MANUAL:
            return settings.language, 1.0
        if self.engine is None or not hasattr(self.engine, "detect_language"):
            raise TranscriptionError("Language auto-detection requires an engine")
        try:
            language, probability = self.engine.detect_language(audio)
        except (UnsupportedLanguageError, TranscriptionError):
            raise
        except Exception as exc:  # pragma: no cover - engine-specific
            raise TranscriptionError(f"Language detection failed: {exc}") from exc
        return str(language), float(probability)
