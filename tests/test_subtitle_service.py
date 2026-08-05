"""SubtitleService: pipeline stage runners, export, full pipeline integration."""

from pathlib import Path

import pytest

from src.ai.whisper.result import Segment, TranscriptResult
from src.core.pipeline import (
    Pipeline,
    PipelineCancelledError,
    PipelineContext,
    PipelineError,
    PipelineStage,
)
from src.models.job_model import Job
from src.subtitles.settings import SubtitleSettings
from src.subtitles.subtitle_service import SubtitleService


def _transcript() -> TranscriptResult:
    return TranscriptResult(
        language="en",
        duration=6.0,
        segments=[
            Segment(0.0, 2.0, "Hello everyone, welcome back."),
            Segment(2.5, 4.0, "Today we talk about captions."),
            Segment(4.5, 6.0, "Thanks for watching."),
        ],
    )


def _overlapping_transcript() -> TranscriptResult:
    return TranscriptResult(
        language="en",
        segments=[
            Segment(0.0, 3.0, "First caption"),
            Segment(2.0, 5.0, "Second caption overlaps"),
        ],
    )


@pytest.fixture
def service(config, tmp_path) -> SubtitleService:
    return SubtitleService(config, subtitles_dir=tmp_path / "subtitles")


def _ctx(tmp_path, *, transcript=True, cancelled=False, audio=True) -> PipelineContext:
    ctx = PipelineContext(
        job_id="j1",
        video_path=str(tmp_path / "clip.mp4"),
        filename="clip.mp4",
        audio_path=str(tmp_path / "clip.wav") if audio else "",
    )
    if transcript:
        ctx.transcript = _transcript().to_dict()
    if cancelled:
        ctx.cancel()
    return ctx


# ------------------------------------------------------------- enablement
def test_enabled_from_config(service, config):
    assert service.enabled() is True  # default auto_generate
    config.set("subtitles", {**config.get("subtitles", {}), "auto_generate": False})
    assert service.enabled() is False


def test_available_formats(service):
    assert set(service.available_formats()) == {"srt", "ass", "vtt", "json", "txt"}


# -------------------------------------------------------------- generation
def test_stage_runner_generates_and_saves(service, tmp_path):
    ctx = _ctx(tmp_path)
    service.stage_runner()(ctx)

    assert ctx.subtitle_path
    assert set(ctx.subtitle_formats) == {"srt", "ass", "vtt", "json", "txt"}
    for path in ctx.subtitle_formats.values():
        assert Path(path).exists()
    assert Path(ctx.subtitle_path).suffix == ".srt"
    assert isinstance(ctx.subtitle_warnings, list)


def test_stage_runner_without_transcript_raises(service, tmp_path):
    ctx = _ctx(tmp_path, transcript=False)
    with pytest.raises(PipelineError, match="No transcript"):
        service.stage_runner()(ctx)


def test_stage_runner_respects_cancellation(service, tmp_path):
    ctx = _ctx(tmp_path, cancelled=True)
    with pytest.raises(PipelineCancelledError):
        service.stage_runner()(ctx)


def test_stage_runner_maps_subtitle_error_to_pipeline_error(service, tmp_path):
    ctx = _ctx(tmp_path)
    ctx.transcript = TranscriptResult(
        language="en",
        segments=[Segment(0.0, 1.0, "   ")],  # no speech -> EmptySubtitleError
    ).to_dict()
    with pytest.raises(PipelineError, match="Subtitle generation failed"):
        service.stage_runner()(ctx)


# -------------------------------------------------------------- validation
def test_validation_runner_balanced_records_warnings(service, config, tmp_path):
    config.set("subtitles", {**config.get("subtitles", {}), "timing_optimization": False})
    ctx = _ctx(tmp_path)
    ctx.transcript = TranscriptResult(
        language="en",
        segments=[Segment(0.0, 0.5, "x" * 30)],  # 60 cps -> reading-speed warning
    ).to_dict()

    service.validation_runner()(ctx)
    assert any("reading speed" in w.lower() or "cps" in w for w in ctx.subtitle_warnings)


def test_validation_runner_strict_fails_on_overlap(service, config, tmp_path):
    config.set("subtitles", {
        **config.get("subtitles", {}),
        "validation_strictness": "strict",
        "timing_optimization": False,  # keep the raw overlap for validation
    })
    ctx = _ctx(tmp_path)
    ctx.transcript = _overlapping_transcript().to_dict()

    with pytest.raises(PipelineError, match="(?i)overlap"):
        service.validation_runner()(ctx)


def test_validation_runner_strict_passes_clean_document(service, config, tmp_path):
    config.set("subtitles", {**config.get("subtitles", {}), "validation_strictness": "strict"})
    ctx = _ctx(tmp_path)
    service.validation_runner()(ctx)  # clean transcript — must not raise
    assert ctx.subtitle_warnings == []


# ------------------------------------------------------------------ export
def test_export_writes_file(service, tmp_path):
    job = Job(filename="clip.mp4", path=str(tmp_path / "clip.mp4"), transcript=_transcript().to_dict())
    folder = tmp_path / "export"
    target = service.export(job, "srt", folder)

    assert target.exists()
    assert target.suffix == ".srt"
    assert target.read_text(encoding="utf-8").startswith("1\n")


def test_export_unsupported_format(service, tmp_path):
    job = Job(filename="clip.mp4", path=str(tmp_path / "clip.mp4"), transcript=_transcript().to_dict())
    from src.subtitles.exceptions import UnsupportedFormatError

    with pytest.raises(UnsupportedFormatError):
        service.export(job, "scc", tmp_path)


def test_export_without_transcript_raises(service, tmp_path):
    job = Job(filename="clip.mp4", path=str(tmp_path / "clip.mp4"))
    with pytest.raises(PipelineError, match="has no transcript"):
        service.export(job, "srt", tmp_path)


def test_export_respects_custom_settings(service, tmp_path):
    job = Job(filename="clip.mp4", path=str(tmp_path / "clip.mp4"), transcript=_transcript().to_dict())
    settings = SubtitleSettings(default_format="vtt", max_chars_per_line=30)
    target = service.export(job, "vtt", tmp_path, settings=settings)
    assert target.suffix == ".vtt"
    assert target.read_text(encoding="utf-8").startswith("WEBVTT")


# ------------------------------------------------------ pipeline integration
def test_subtitle_stages_in_real_pipeline(service, tmp_path):
    pipeline = Pipeline()
    pipeline.register(PipelineStage.IMPORTED, lambda ctx: None)

    def transcribe(ctx: PipelineContext) -> None:
        ctx.transcript = _transcript().to_dict()

    pipeline.register(PipelineStage.TRANSCRIPTION_READY, transcribe)
    pipeline.register(PipelineStage.SUBTITLE_READY, service.stage_runner())
    pipeline.register(PipelineStage.SUBTITLE_VALIDATED, service.validation_runner())

    ctx = _ctx(tmp_path, audio=False)
    assert pipeline.run(ctx) is PipelineStage.COMPLETED
    assert ctx.subtitle_path and Path(ctx.subtitle_path).exists()
    assert ctx.stage is PipelineStage.SUBTITLE_VALIDATED


def test_stage_runners_report_progress(service, tmp_path):
    ctx = _ctx(tmp_path)
    seen: list[float] = []

    def funnel(stage, fraction) -> None:
        seen.append(ctx.progress)

    ctx.on_progress = funnel
    service.stage_runner()(ctx)
    service.validation_runner()(ctx)
    assert seen == sorted(seen)
    assert seen  # progress was reported at least once


def test_save_all_uses_collision_safe_names(service, tmp_path):
    ctx = _ctx(tmp_path)
    paths = service.save_all(service.engine.build(_transcript(), service.settings()), tmp_path / "clip.mp4")
    assert len(paths) == 5
    names = {p.name for p in paths.values()}
    assert len(names) == 5  # distinct extensions


def test_job_model_exposes_subtitle_fields(config, tmp_path):
    job = Job(filename="clip.mp4", path=str(tmp_path / "clip.mp4"))
    assert job.subtitle_path == ""
    assert job.subtitle_warnings == []
    data = job.to_dict()
    assert data["subtitle_path"] == ""
    assert data["subtitle_warnings"] == []
