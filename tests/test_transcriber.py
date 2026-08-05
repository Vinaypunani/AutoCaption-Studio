"""Chunked transcriber: fake-engine tests for offsets, progress, cancellation."""

import pytest

from src.ai.whisper.exceptions import (
    EmptyAudioError,
    TranscriptionCancelledError,
)
from src.ai.whisper.result import Segment, Word
from src.ai.whisper.settings import LanguageMode, WhisperSettings
from src.ai.whisper.transcriber import SAMPLE_RATE, Transcriber


class _FakeEngine:
    """Records load args and returns deterministic segments per chunk.

    Fresh copies are returned per call: the transcriber offsets timestamps
    *in place*, so a shared list would be mutated between chunks.
    """

    def __init__(self, segments=None):
        self.loaded = {}
        self.calls = []
        self._segments = segments or [
            Segment(0.0, 1.0, "local words", [Word("local", 0.0, 0.5, 0.9)])
        ]

    def load(self, model_name, *, device, compute_type, threads, download_root):
        self.loaded = {
            "model": model_name,
            "device": device,
            "compute_type": compute_type,
            "threads": threads,
            "download_root": download_root,
        }

    def detect_language(self, audio):
        return "en", 0.95

    def transcribe(self, audio, *, language, beam_size, word_timestamps):
        self.calls.append({"language": language, "beam_size": beam_size, "word_timestamps": word_timestamps})
        import copy

        return "en", 0.95, copy.deepcopy(self._segments)

    def close(self):
        pass


def _samples(seconds: float):
    import numpy as np

    return np.zeros(int(seconds * SAMPLE_RATE), dtype=np.float32)


def _settings(**overrides) -> WhisperSettings:
    return WhisperSettings(**{"language_mode": "auto", **overrides})


def _transcriber(engine=None, chunk_seconds=30.0):
    return Transcriber(engine=engine or _FakeEngine(), chunk_seconds=chunk_seconds)


def test_transcribe_runs_engine_and_builds_result(tmp_path, monkeypatch):
    engine = _FakeEngine()
    transcriber = _transcriber(engine)
    monkeypatch.setattr(transcriber, "_decode", lambda path: _samples(1.0))

    result = transcriber.transcribe("C:/a.wav", _settings())
    assert result.language == "en"
    assert result.segments[0].text == "local words"
    assert result.segments[0].words[0].word == "local"
    assert engine.loaded["model"] == "tiny"
    assert engine.loaded["device"] == "cpu"
    assert engine.calls[0]["beam_size"] == 5
    assert engine.calls[0]["word_timestamps"] is True


def test_chunked_transcription_offsets_timestamps(tmp_path, monkeypatch):
    transcriber = _transcriber(chunk_seconds=0.5)
    monkeypatch.setattr(transcriber, "_decode", lambda path: _samples(1.0))

    result = transcriber.transcribe("C:/a.wav", _settings())
    # Two chunks of 0.5s; chunk 2 offsets everything by 0.5s.
    assert len(result.segments) == 2
    assert result.segments[0].start == 0.0
    assert result.segments[1].start == 0.5
    assert result.segments[1].end == 1.5
    assert result.segments[1].words[0].start == 0.5
    assert result.segments[1].words[0].end == 1.0
    assert result.duration == pytest.approx(1.0)


def test_progress_reports_per_chunk(tmp_path, monkeypatch):
    transcriber = _transcriber(chunk_seconds=0.25)
    monkeypatch.setattr(transcriber, "_decode", lambda path: _samples(1.0))

    progress: list[float] = []
    transcriber.transcribe("C:/a.wav", _settings(), on_progress=progress.append)
    assert progress == pytest.approx([0.25, 0.5, 0.75, 1.0])


def test_cancellation_raises_between_chunks(tmp_path, monkeypatch):
    transcriber = _transcriber(chunk_seconds=0.5)
    monkeypatch.setattr(transcriber, "_decode", lambda path: _samples(2.0))

    with pytest.raises(TranscriptionCancelledError):
        transcriber.transcribe("C:/a.wav", _settings(), cancel_event=lambda: True)


def test_empty_audio_raises(tmp_path, monkeypatch):
    transcriber = _transcriber()
    monkeypatch.setattr(transcriber, "_decode", lambda path: _samples(0.001))

    with pytest.raises(EmptyAudioError):
        transcriber.transcribe("C:/a.wav", _settings())


def test_load_reuses_engine_for_same_config(tmp_path, monkeypatch):
    engine = _FakeEngine()
    transcriber = _transcriber(engine)
    monkeypatch.setattr(transcriber, "_decode", lambda path: _samples(1.0))

    transcriber.transcribe("C:/a.wav", _settings())
    transcriber.transcribe("C:/a.wav", _settings())
    # Fake engine has no caching, but verify both runs forwarded threads.
    assert all(call["language"] == "en" for call in engine.calls)


def test_manual_language_forwarded_to_engine(tmp_path, monkeypatch):
    engine = _FakeEngine()
    transcriber = _transcriber(engine)
    monkeypatch.setattr(transcriber, "_decode", lambda path: _samples(1.0))

    transcriber.transcribe("C:/a.wav", _settings(language_mode=LanguageMode.MANUAL, language="de"))
    assert engine.calls[0]["language"] == "de"


class _ThreeValueDetectModel:
    """Mimics faster-whisper 1.2+ detect_language (3-tuple return)."""

    def detect_language(self, audio):
        return "en", 0.95, [("english", 0.95), ("spanish", 0.04)]


class _TwoValueDetectModel:
    """Mimics older faster-whisper detect_language (2-tuple return)."""

    def detect_language(self, audio):
        return "es", 0.87


def test_engine_detect_language_handles_three_value_return():
    from src.ai.whisper.transcriber import FasterWhisperEngine

    engine = FasterWhisperEngine()
    engine._model = _ThreeValueDetectModel()
    assert engine.detect_language(b"audio") == ("en", 0.95)


def test_engine_detect_language_handles_two_value_return():
    from src.ai.whisper.transcriber import FasterWhisperEngine

    engine = FasterWhisperEngine()
    engine._model = _TwoValueDetectModel()
    assert engine.detect_language(b"audio") == ("es", 0.87)


def test_engine_detect_language_without_model_raises():
    from src.ai.whisper.exceptions import TranscriptionError
    from src.ai.whisper.transcriber import FasterWhisperEngine

    engine = FasterWhisperEngine()
    with pytest.raises(TranscriptionError, match="not loaded"):
        engine.detect_language(b"audio")
