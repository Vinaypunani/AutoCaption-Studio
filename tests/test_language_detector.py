"""Language detection: auto vs manual, engine delegation, error cases."""

import pytest

from src.ai.whisper.exceptions import TranscriptionError, UnsupportedLanguageError
from src.ai.whisper.language_detector import LanguageDetector
from src.ai.whisper.settings import LanguageMode, WhisperSettings


class _FakeEngine:
    def __init__(self, language="en", probability=0.99):
        self.language = language
        self.probability = probability

    def detect_language(self, audio):
        return self.language, self.probability


def test_manual_mode_returns_configured_language():
    settings = WhisperSettings(language_mode=LanguageMode.MANUAL, language="fr")
    detector = LanguageDetector(engine=None)  # no engine needed for manual
    assert detector.resolve(b"audio", settings) == ("fr", 1.0)


def test_auto_mode_uses_engine():
    settings = WhisperSettings(language_mode=LanguageMode.AUTO)
    detector = LanguageDetector(engine=_FakeEngine("es", 0.87))
    assert detector.resolve(b"audio", settings) == ("es", 0.87)


def test_auto_mode_without_engine_raises():
    settings = WhisperSettings(language_mode=LanguageMode.AUTO)
    detector = LanguageDetector(engine=None)
    with pytest.raises(TranscriptionError, match="requires an engine"):
        detector.resolve(b"audio", settings)


def test_engine_failure_is_wrapped():
    class _BrokenEngine:
        def detect_language(self, audio):
            raise RuntimeError("engine exploded")

    settings = WhisperSettings(language_mode=LanguageMode.AUTO)
    detector = LanguageDetector(engine=_BrokenEngine())
    with pytest.raises(TranscriptionError, match="engine exploded"):
        detector.resolve(b"audio", settings)


def test_unsupported_language_short_code_rejected():
    settings = WhisperSettings(language_mode=LanguageMode.MANUAL, language="q")
    detector = LanguageDetector(engine=None)
    with pytest.raises(UnsupportedLanguageError):
        detector.resolve(b"audio", settings)


def test_known_manual_language_passes_validation():
    settings = WhisperSettings(language_mode=LanguageMode.MANUAL, language="de")
    assert LanguageDetector(engine=None).resolve(b"audio", settings) == ("de", 1.0)
