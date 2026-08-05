"""Job pipeline (src/core/pipeline.py): stage ordering, progress, cancellation."""

import pytest

from src.core.pipeline import (
    PIPELINE_ORDER,
    Pipeline,
    PipelineCancelledError,
    PipelineContext,
    PipelineError,
    PipelineStage,
)


def _ctx() -> PipelineContext:
    return PipelineContext(job_id="j1", video_path="C:/v.mp4", filename="v.mp4")


def _noop(stage: PipelineStage) -> None:
    def runner(ctx: PipelineContext) -> None:
        ctx.set_progress(stage, 1.0)

    return runner


def test_pipeline_order_is_expected():
    assert [s.value for s in PIPELINE_ORDER] == [
        "Imported",
        "Validated",
        "Metadata Ready",
        "Thumbnail Ready",
        "Audio Ready",
        "Transcription Ready",
        "Subtitle Ready",
        "Subtitle Validated",
        "Render Ready",
        "Completed",
    ]


def test_pipeline_runs_all_registered_stages_in_order():
    pipeline = Pipeline()
    pipeline.register(PipelineStage.IMPORTED, _noop(PipelineStage.IMPORTED))
    pipeline.register(PipelineStage.VALIDATED, _noop(PipelineStage.VALIDATED))
    pipeline.register(PipelineStage.METADATA_READY, _noop(PipelineStage.METADATA_READY))
    assert [s.value for s in pipeline.stages()] == ["Imported", "Validated", "Metadata Ready"]

    ctx = _ctx()
    terminal = pipeline.run(ctx)
    assert terminal is PipelineStage.COMPLETED
    assert ctx.progress == 100.0


def test_pipeline_stage_alias_backward_compat():
    assert PipelineStage.VALIDATING is PipelineStage.VALIDATED
    assert PipelineStage.READING_METADATA is PipelineStage.METADATA_READY
    assert PipelineStage.GENERATING_THUMBNAIL is PipelineStage.THUMBNAIL_READY
    assert PipelineStage.EXTRACTING_AUDIO is PipelineStage.AUDIO_READY
    assert PipelineStage.READY is PipelineStage.COMPLETED


def test_pipeline_cancellation_raises():
    pipeline = Pipeline()
    pipeline.register(PipelineStage.IMPORTED, _noop(PipelineStage.IMPORTED))
    pipeline.register(PipelineStage.VALIDATED, _noop(PipelineStage.VALIDATED))

    ctx = _ctx()
    ctx.cancel()
    with pytest.raises(PipelineCancelledError):
        pipeline.run(ctx)


def test_pipeline_cancel_event_callback():
    pipeline = Pipeline()
    pipeline.register(PipelineStage.IMPORTED, _noop(PipelineStage.IMPORTED))

    ctx = _ctx()
    ctx.cancel_event = lambda: True
    with pytest.raises(PipelineCancelledError):
        pipeline.run(ctx)


def test_pipeline_wraps_unknown_stage_failure():
    def bad_runner(ctx: PipelineContext) -> None:
        raise ValueError("boom")

    pipeline = Pipeline()
    pipeline.register(PipelineStage.IMPORTED, bad_runner)

    ctx = _ctx()
    with pytest.raises(PipelineError, match="Imported failed: boom"):
        pipeline.run(ctx)
    assert "Imported failed: boom" in ctx.error


def test_pipeline_propagates_pipeline_error_as_is():
    def bad_runner(ctx: PipelineContext) -> None:
        raise PipelineError("custom failure")

    pipeline = Pipeline()
    pipeline.register(PipelineStage.IMPORTED, bad_runner)

    with pytest.raises(PipelineError, match="custom failure"):
        pipeline.run(_ctx())


def _record_runner(stage: PipelineStage, seen: list):
    def runner(ctx: PipelineContext) -> None:
        ctx.set_progress(stage, 1.0)
        seen.append(ctx.progress)

    return runner


def test_overall_progress_monotonic_and_ends_at_100():
    pipeline = Pipeline()
    seen: list[float] = []
    for stage in (
        PipelineStage.IMPORTED,
        PipelineStage.VALIDATED,
        PipelineStage.METADATA_READY,
        PipelineStage.THUMBNAIL_READY,
        PipelineStage.AUDIO_READY,
        PipelineStage.TRANSCRIPTION_READY,
    ):
        pipeline.register(stage, _record_runner(stage, seen))

    pipeline.run(_ctx())

    assert seen == sorted(seen)  # monotonic
    assert seen[-1] < 100.0  # 100 is only reached at the very end
    assert pipeline.run(_ctx()) is PipelineStage.COMPLETED


def test_sub_stage_progress_maps_to_container_weight():
    pipeline = Pipeline()
    for stage in (
        PipelineStage.IMPORTED,  # 2
        PipelineStage.VALIDATED,  # 6
        PipelineStage.METADATA_READY,  # 17
        PipelineStage.THUMBNAIL_READY,  # 12
        PipelineStage.AUDIO_READY,  # 18
    ):
        pipeline.register(stage, _noop(stage))

    captured: list[float] = []

    def runner(ctx: PipelineContext) -> None:
        ctx.set_progress(PipelineStage.TRANSCRIBING, 0.5)
        captured.append(ctx.progress)

    pipeline.register(PipelineStage.TRANSCRIPTION_READY, runner)

    pipeline.run(_ctx())
    # 55 base before transcription + 40 * 0.5 = 75
    assert captured == [75.0]


def test_pipeline_unregistered_stage_is_skipped():
    pipeline = Pipeline()
    pipeline.register(PipelineStage.AUDIO_READY, _noop(PipelineStage.AUDIO_READY))
    ctx = _ctx()
    assert pipeline.run(ctx) is PipelineStage.COMPLETED
