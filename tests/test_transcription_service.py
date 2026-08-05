"""TranscriptionService: enablement, model management, pipeline stage runner."""

from pathlib import Path

import pytest

from src.ai.whisper.cache import TranscriptStore
from src.ai.whisper.result import Segment, TranscriptResult
from src.core.pipeline import (
    PipelineCancelledError,
    PipelineContext,
    PipelineError,
    PipelineStage,
)
from src.services.transcription_service import TranscriptionService


class _FakeTranscriber:
    def __init__(self, result=None):
        self.result = result or TranscriptResult(
            language="en",
            duration=1.0,
            segments=[Segment(0.0, 1.0, "hello there", words=[])],
        )
        self.calls = 0

    def transcribe(self, audio_path, settings, *, on_progress=None, cancel_event=None, model_dir=None):
        self.calls += 1
        if on_progress is not None:
            on_progress(1.0)
        return self.result


class _FakeModelManager:
    def __init__(self, models_dir, installed=False):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.installed = installed
        self.downloaded = []

    def is_installed(self, name):
        return self.installed

    def model_dir(self, name):
        return self.models_dir / name

    def download(self, name, on_progress=None):
        self.downloaded.append(name)
        directory = self.models_dir / name
        directory.mkdir(parents=True, exist_ok=True)
        return directory


@pytest.fixture
def service(config, tmp_path):
    store = TranscriptStore(tmp_path / "transcripts")
    return TranscriptionService(
        config,
        model_manager=_FakeModelManager(tmp_path / "models", installed=True),
        transcriber=_FakeTranscriber(),
        store=store,
    )


def _ctx(tmp_path, *, audio=True, cancelled=False) -> PipelineContext:
    video = tmp_path / "clip.mp4"
    audio_path = tmp_path / "clip.wav"
    if audio:
        audio_path.write_bytes(b"RIFFfake")
    ctx = PipelineContext(job_id="j1", video_path=str(video), filename="clip.mp4", audio_path=str(audio_path))
    if cancelled:
        ctx.cancel()
    return ctx


def _service(config, tmp_path) -> TranscriptionService:
    return TranscriptionService(
        config,
        model_manager=_FakeModelManager(tmp_path / "models", installed=True),
        store=TranscriptStore(tmp_path / "transcripts"),
    )


def test_enabled_respects_auto_transcribe_flag(config, tmp_path):
    # Config defaults have auto_transcribe True and faster-whisper is installed.
    assert _service(config, tmp_path).enabled() is True

    config.set("whisper", {**config.get("whisper", {}), "auto_transcribe": False})
    assert _service(config, tmp_path).enabled() is False


def test_model_installed_queries_manager(service, tmp_path):
    assert service.model_installed("tiny") is True
    service.model_manager.installed = False
    assert service.model_installed("tiny") is False


def test_install_model_uses_cache_when_installed(config, tmp_path):
    fake = _FakeModelManager(tmp_path / "models", installed=True)
    service = TranscriptionService(config, model_manager=fake)
    result = service.install_model()
    assert result == fake.models_dir / "tiny"
    assert fake.downloaded == []


def test_install_model_downloads_when_missing(config, tmp_path):
    fake = _FakeModelManager(tmp_path / "models", installed=False)
    service = TranscriptionService(config, model_manager=fake)
    result = service.install_model()
    assert result == fake.models_dir / "tiny"
    assert fake.downloaded == ["tiny"]


def test_stage_runner_transcribes_and_saves(service, tmp_path):
    runner = service.stage_runner()
    ctx = _ctx(tmp_path)

    runner(ctx)

    assert service.transcriber.calls == 1
    assert ctx.transcript is not None
    assert ctx.transcript["segments"][0]["text"] == "hello there"
    assert ctx.transcript_path
    assert Path(ctx.transcript_path).exists()
    assert service.store.exists(ctx.video_path)


def test_stage_runner_reuses_cache_without_transcribing(service, tmp_path):
    ctx = _ctx(tmp_path)
    service.store.save(service.transcriber.result, ctx.video_path)

    runner = service.stage_runner()
    runner(ctx)

    assert service.transcriber.calls == 0  # cache hit — engine never runs
    assert ctx.transcript["segments"][0]["text"] == "hello there"
    assert ctx.transcript_path == str(service.store.json_path(ctx.video_path))


def test_stage_runner_without_audio_raises(service, tmp_path):
    runner = service.stage_runner()
    ctx = _ctx(tmp_path, audio=False)
    with pytest.raises(PipelineError, match="No audio"):
        runner(ctx)


def test_stage_runner_respects_cancellation(service, tmp_path):
    runner = service.stage_runner()
    ctx = _ctx(tmp_path, cancelled=True)
    with pytest.raises(PipelineCancelledError):
        runner(ctx)
    assert service.transcriber.calls == 0


def test_stage_runner_installed_in_pipeline(service, tmp_path):
    from src.core.pipeline import Pipeline

    pipeline = Pipeline()
    pipeline.register(PipelineStage.IMPORTED, lambda ctx: None)
    pipeline.register(PipelineStage.TRANSCRIPTION_READY, service.stage_runner())

    ctx = _ctx(tmp_path)
    assert pipeline.run(ctx) is PipelineStage.COMPLETED
    assert service.store.exists(ctx.video_path)
