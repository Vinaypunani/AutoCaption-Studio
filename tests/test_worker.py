"""TranscriptionWorker: QThread wrapper success / cancel / failure paths."""

import time

from PySide6.QtWidgets import QApplication

from src.ai.whisper.exceptions import TranscriptionError
from src.ai.whisper.result import Segment, TranscriptResult
from src.ai.whisper.settings import WhisperSettings
from src.ai.whisper.worker import (
    STAGE_COMPLETED,
    STAGE_LOADING,
    STAGE_PREPARING,
    STAGE_TRANSCRIBING,
    TranscriptionWorker,
)


class _FakeTranscriber:
    def __init__(self, result=None, error=None):
        self.result = result or TranscriptResult(
            language="en",
            segments=[Segment(0.0, 1.0, "hello world")],
        )
        self.error = error

    def transcribe(self, audio_path, settings, *, on_progress=None, cancel_event=None, model_dir=None):
        if cancel_event is not None and cancel_event():
            from src.ai.whisper.exceptions import TranscriptionCancelledError

            raise TranscriptionCancelledError("cancelled")
        if self.error is not None:
            raise self.error
        if on_progress is not None:
            on_progress(1.0)
        return self.result


def _pump_until(app, predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        app.processEvents()
        time.sleep(0.02)
    raise AssertionError("timed out waiting for worker signal")


def test_worker_emits_stages_and_success(qapp):
    worker = TranscriptionWorker(_FakeTranscriber(), "C:/a.wav", WhisperSettings())
    stages: list[tuple[str, float]] = []
    results = []
    worker.progress_changed.connect(lambda stage, frac: stages.append((stage, frac)))
    worker.succeeded.connect(results.append)

    worker.start()
    _pump_until(qapp, lambda: bool(results))

    labels = [label for label, _ in stages]
    assert STAGE_PREPARING in labels
    assert STAGE_LOADING in labels
    assert STAGE_TRANSCRIBING in labels
    assert labels[-1] == STAGE_COMPLETED
    assert results[0].segments[0].text == "hello world"
    worker.wait(5000)


def test_worker_cancel_emits_cancelled(qapp):
    worker = TranscriptionWorker(_FakeTranscriber(), "C:/a.wav", WhisperSettings())
    cancelled = []
    worker.cancelled.connect(lambda: cancelled.append(True))
    worker.cancel()
    worker.start()
    _pump_until(qapp, lambda: bool(cancelled))
    worker.wait(5000)


def test_worker_failure_emits_error_message(qapp):
    worker = TranscriptionWorker(
        _FakeTranscriber(error=TranscriptionError("model blew up")),
        "C:/a.wav",
        WhisperSettings(),
    )
    errors = []
    worker.failed.connect(errors.append)
    worker.start()
    _pump_until(qapp, lambda: bool(errors))
    assert "model blew up" in errors[0]
    worker.wait(5000)


def test_worker_forwards_model_dir_and_settings(qapp):
    class _RecordingTranscriber(_FakeTranscriber):
        def __init__(self):
            super().__init__()
            self.seen = None

        def transcribe(self, audio_path, settings, *, on_progress=None, cancel_event=None, model_dir=None):
            self.seen = (audio_path, settings.model, model_dir)
            return self.result

    fake = _RecordingTranscriber()
    worker = TranscriptionWorker(fake, "C:/clip.wav", WhisperSettings(model="small"), model_dir="C:/models")
    results = []
    worker.succeeded.connect(results.append)
    worker.start()
    _pump_until(qapp, lambda: bool(results))
    assert fake.seen[0] == "C:/clip.wav"
    assert fake.seen[1] == "small"
    assert fake.seen[2] == "C:/models"
    worker.wait(5000)
