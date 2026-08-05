"""Job pipeline — the processing backbone.

Defines the ordered stages a video job flows through and lets services
register a *runner* for each stage. Every stage consumes the artifacts
produced by the previous ones (stored on :class:`PipelineContext`), so
modules never call each other directly:

    Imported → Validated → Metadata Ready → Thumbnail Ready → Audio Ready
    → Transcription Ready → Subtitle Ready → Render Ready → Completed

Retries, cancellations and future stages (translation, speaker diarization,
emoji insertion) all hang off this structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Protocol

from ..video.metadata import VideoMetadata
from .logger import get_logger

log = get_logger("pipeline")


class PipelineStage(str, Enum):
    """Every stage a job can reach (also used as the job's stage display).

    ``WAITING`` / ``FAILED`` / ``CANCELLED`` are terminal display states,
    not pipeline stages. Aliases keep the earlier Phase 2 names working.
    """

    # -- pipeline order -----------------------------------------------------
    IMPORTED = "Imported"
    VALIDATED = "Validated"
    METADATA_READY = "Metadata Ready"
    THUMBNAIL_READY = "Thumbnail Ready"
    AUDIO_READY = "Audio Ready"
    TRANSCRIPTION_READY = "Transcription Ready"
    SUBTITLE_READY = "Subtitle Ready"
    RENDER_READY = "Render Ready"
    COMPLETED = "Completed"

    # -- display / terminal states ------------------------------------------
    WAITING = "Waiting"
    TRANSCRIBING = "Transcribing"  # sub-stage of TRANSCRIPTION_READY
    FAILED = "Failed"
    CANCELLED = "Cancelled"

    # -- backward-compatible aliases ----------------------------------------
    VALIDATING = VALIDATED
    READING_METADATA = METADATA_READY
    GENERATING_THUMBNAIL = THUMBNAIL_READY
    EXTRACTING_AUDIO = AUDIO_READY
    READY = COMPLETED


PIPELINE_ORDER: tuple[PipelineStage, ...] = (
    PipelineStage.IMPORTED,
    PipelineStage.VALIDATED,
    PipelineStage.METADATA_READY,
    PipelineStage.THUMBNAIL_READY,
    PipelineStage.AUDIO_READY,
    PipelineStage.TRANSCRIPTION_READY,
    PipelineStage.SUBTITLE_READY,
    PipelineStage.RENDER_READY,
    PipelineStage.COMPLETED,
)


class PipelineError(Exception):
    """Base error for pipeline execution."""


class PipelineCancelledError(PipelineError):
    """Raised when a job is cancelled mid-pipeline."""


@dataclass
class PipelineContext:
    """Shared artifacts + state flowing through the stages of one job."""

    job_id: str
    video_path: str
    filename: str

    metadata: Optional[VideoMetadata] = None
    thumbnail_path: str = ""
    audio_path: str = ""
    transcript_path: str = ""
    transcript: Optional[dict] = None

    stage: PipelineStage = PipelineStage.IMPORTED
    progress: float = 0.0
    cancelled: bool = False
    error: str = ""

    # Callbacks installed by the pipeline runner.
    on_progress: Optional[Callable[[PipelineStage, float], None]] = None
    cancel_event: Optional[Callable[[], bool]] = None

    def cancel(self) -> None:
        self.cancelled = True

    def is_cancelled(self) -> bool:
        if self.cancelled:
            return True
        return bool(self.cancel_event and self.cancel_event())

    def set_progress(self, stage: PipelineStage, fraction: float) -> None:
        """Report stage progress (0..1); forwarded to the runner thread."""
        if self.on_progress is not None:
            self.on_progress(stage, max(0.0, min(1.0, fraction)))


class StageRunner(Protocol):
    """A callable that advances the pipeline by one stage."""

    def __call__(self, ctx: PipelineContext) -> None: ...  # pragma: no cover


# Sub-stages report progress against their container stage's weight.
_SUB_STAGES: dict[PipelineStage, tuple[PipelineStage, ...]] = {
    PipelineStage.TRANSCRIPTION_READY: (PipelineStage.TRANSCRIBING,),
}

# Default per-stage weight of overall progress (sums to 100).
_DEFAULT_WEIGHTS: dict[PipelineStage, float] = {
    PipelineStage.IMPORTED: 2,
    PipelineStage.VALIDATED: 6,
    PipelineStage.METADATA_READY: 17,
    PipelineStage.THUMBNAIL_READY: 12,
    PipelineStage.AUDIO_READY: 18,
    PipelineStage.TRANSCRIPTION_READY: 40,
    PipelineStage.SUBTITLE_READY: 3,
    PipelineStage.RENDER_READY: 1,
    PipelineStage.COMPLETED: 1,
}


class Pipeline:
    """Ordered registry of stage runners, executed against a context."""

    def __init__(self) -> None:
        self._runners: dict[PipelineStage, StageRunner] = {}
        self._weights: dict[PipelineStage, float] = dict(_DEFAULT_WEIGHTS)

    # -- registration --------------------------------------------------------
    def register(self, stage: PipelineStage, runner: StageRunner, weight: Optional[float] = None) -> None:
        """Attach a runner for a stage; ``weight`` tunes its progress share."""
        self._runners[stage] = runner
        if weight is not None:
            self._weights[stage] = weight

    def has_stage(self, stage: PipelineStage) -> bool:
        return stage in self._runners

    # -- execution -------------------------------------------------------------
    def stages(self) -> list[PipelineStage]:
        """Registered stages in pipeline order."""
        return [stage for stage in PIPELINE_ORDER if stage in self._runners]

    def _overall_progress(self, stage: PipelineStage, fraction: float) -> float:
        stages = self.stages()
        if not stages:
            return fraction
        weight_key = stage
        for container, sub_stages in _SUB_STAGES.items():
            if stage in sub_stages:
                weight_key = container
                break
        base = 0.0
        for registered in stages:
            if registered is weight_key:
                break
            base += self._weights.get(registered, 0.0)
        return min(100.0, base + self._weights.get(weight_key, 0.0) * fraction)

    def run(self, ctx: PipelineContext) -> PipelineStage:
        """Execute every registered stage; returns the terminal stage reached.

        Raises :class:`PipelineCancelledError` on cancellation and
        :class:`PipelineError` when a stage fails (its message is left on
        ``ctx.error``).
        """
        # The caller (worker thread) may have installed a progress funnel;
        # keep it chained so stage updates still reach the UI as they happen.
        funnel = ctx.on_progress
        for stage in self.stages():
            if ctx.is_cancelled():
                raise PipelineCancelledError(f"Cancelled before {stage.value}")
            ctx.stage = stage
            runner = self._runners[stage]

            def _report(stage=stage, fraction: float = 0.0) -> None:  # noqa: B008
                ctx.progress = self._overall_progress(stage, fraction)
                if funnel is not None:
                    funnel(stage, fraction)

            # Give the runner a progress funnel that updates overall progress.
            ctx.on_progress = _report
            try:
                runner(ctx)
            except PipelineError:
                raise
            except Exception as exc:  # pragmatic: wrap unknown failures
                ctx.error = f"{stage.value} failed: {exc}"
                log.exception("Pipeline stage %s failed for %s", stage.value, ctx.job_id)
                raise PipelineError(ctx.error) from exc
            log.info("Stage complete: %s (%s)", stage.value, ctx.filename)

        ctx.progress = 100.0
        return PipelineStage.COMPLETED
