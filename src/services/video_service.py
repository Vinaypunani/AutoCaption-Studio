"""Video pipeline service (Phase 2 media stages + Phase 3 hooks).

Every job runs through the shared :class:`Pipeline` on its own worker
thread. Phase 2 stages (validate → metadata → thumbnail → audio) are always
registered; the transcription stage is added by :class:`TranscriptionService`
when available. Jobs can be cancelled between stages.
"""

from __future__ import annotations

import copy
import time
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from ..core.app_state import AppState
from ..core.logger import get_logger
from ..core.pipeline import (
    Pipeline,
    PipelineCancelledError,
    PipelineContext,
    PipelineError,
    PipelineStage,
)
from ..models.job_model import Job, JobStatus
from ..video import FileManager, FFmpegManager
from ..video.exceptions import VideoProcessingError
from ..video.extractor import extract_audio
from ..video.metadata import probe
from ..video.thumbnail import generate_thumbnail
from ..video.validator import validate_extension, validate_file

log = get_logger("video_service")


class _PipelineWorker(QThread):
    """Runs the pipeline for a job *copy* and emits Job snapshots."""

    stage_done = Signal(object)  # Job

    def __init__(
        self,
        job: Job,
        pipeline: Pipeline,
        ctx: PipelineContext,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.job = job
        self.pipeline = pipeline
        self.ctx = ctx
        ctx.on_progress = self._emit_progress
        self._last_emit = 0.0

    def run(self) -> None:  # noqa: C901 - linear orchestration, flat by design
        try:
            self.pipeline.run(self.ctx)
            self.job.status = JobStatus.COMPLETED
            self.job.stage = PipelineStage.COMPLETED
            self.job.progress = 100.0
            self._sync_artifacts()
            self.job.error = ""
            log.info("Pipeline finished: %s", self.job.filename)
        except PipelineCancelledError:
            self.job.status = JobStatus.CANCELLED
            self.job.stage = PipelineStage.CANCELLED
            self.job.error = "Cancelled by user"
            log.info("Pipeline cancelled: %s", self.job.filename)
        except (PipelineError, VideoProcessingError) as exc:
            self.job.status = JobStatus.FAILED
            self.job.stage = PipelineStage.FAILED
            self.job.error = self.ctx.error or str(exc)
            log.error("Job failed (%s): %s", self.job.filename, self.job.error)
        except Exception as exc:  # pragma: no cover - defensive
            self.job.status = JobStatus.FAILED
            self.job.stage = PipelineStage.FAILED
            self.job.error = f"Unexpected error: {exc}"
            log.exception("Unexpected pipeline failure for %s", self.job.filename)
        finally:
            self.stage_done.emit(self.job)

    def _sync_artifacts(self) -> None:
        self.job.metadata = self.ctx.metadata
        self.job.thumbnail_path = self.ctx.thumbnail_path
        self.job.audio_path = self.ctx.audio_path
        self.job.transcript_path = self.ctx.transcript_path
        self.job.transcript = self.ctx.transcript
        self.job.subtitle_path = self.ctx.subtitle_path
        self.job.subtitle_formats = dict(self.ctx.subtitle_formats)
        self.job.subtitle_warnings = list(self.ctx.subtitle_warnings)

    def _emit_progress(self, stage: PipelineStage, fraction: float) -> None:
        self.job.stage = stage
        self.job.progress = self.ctx.progress
        now = time.monotonic()
        if now - self._last_emit >= 0.15 or fraction >= 1.0:
            self._last_emit = now
            self.stage_done.emit(self.job)


class VideoService(QObject):
    """Owns pipeline workers and cancels/stops them on demand."""

    def __init__(
        self,
        app_state: AppState,
        ffmpeg: Optional[FFmpegManager] = None,
        file_manager: Optional[FileManager] = None,
        transcription_service=None,  # services.transcription_service.TranscriptionService
        subtitle_service=None,       # subtitles.subtitle_service.SubtitleService
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_state = app_state
        self.ffmpeg = ffmpeg or FFmpegManager()
        self.file_manager = file_manager or FileManager()
        self.transcription_service = transcription_service
        self.subtitle_service = subtitle_service
        self._workers: dict[str, _PipelineWorker] = {}  # job_id -> worker
        self._contexts: dict[str, PipelineContext] = {}  # job_id -> ctx

        if not self.ffmpeg.available():
            log.warning("FFmpeg unavailable — pipeline is disabled")

    # -- API -----------------------------------------------------------------
    def can_process(self) -> bool:
        return self.ffmpeg.available()

    def ffmpeg_version(self) -> str:
        return self.ffmpeg.version() if self.ffmpeg.available() else "not available"

    def process_job(self, job_id: str) -> None:
        """Start the pipeline for a queued job (no-op if unknown/not processable)."""
        if not self.ffmpeg.available():
            log.warning("Refusing to process %s: ffmpeg unavailable", job_id)
            return
        job = next((j for j in self.app_state.jobs() if j.job_id == job_id), None)
        if job is None or job.demo:
            return
        if job.status is JobStatus.RUNNING:
            return

        ctx = PipelineContext(job_id=job.job_id, video_path=job.path, filename=job.filename)
        self._contexts[job_id] = ctx

        # The worker runs on its own *copy*; AppState.update_job (main thread)
        # is the only writer of the shared state.
        worker = _PipelineWorker(copy.copy(job), self._build_pipeline(), ctx)
        worker.stage_done.connect(self._on_stage_done)
        worker.finished.connect(lambda w=worker, jid=job_id: self._cleanup_worker(jid, w))
        self._workers[job_id] = worker
        log.info("Pipeline started for job %s", job_id)
        worker.start()

    def cancel_job(self, job_id: str) -> None:
        """Request cancellation; takes effect between pipeline stages."""
        ctx = self._contexts.get(job_id)
        if ctx is not None:
            log.info("Cancel requested for job %s", job_id)
            ctx.cancel()
        else:
            # No pipeline running — just clear it from the queue if requested.
            log.info("Cancel requested for idle job %s", job_id)

    def shutdown(self, timeout_ms: int = 5000) -> None:
        """Wait for in-flight workers so the app can exit cleanly."""
        for job_id, worker in list(self._workers.items()):
            if worker.isRunning():
                ctx = self._contexts.get(job_id)
                if ctx is not None:
                    ctx.cancel()
                worker.wait(timeout_ms)
            self._cleanup_worker(job_id, worker)

    # -- pipeline construction ------------------------------------------------
    def _build_pipeline(self) -> Pipeline:
        pipeline = Pipeline()
        pipeline.register(PipelineStage.IMPORTED, lambda ctx: None, weight=2)
        pipeline.register(PipelineStage.VALIDATED, self._run_validation, weight=6)
        pipeline.register(PipelineStage.METADATA_READY, self._run_metadata, weight=17)
        pipeline.register(PipelineStage.THUMBNAIL_READY, self._run_thumbnail, weight=12)
        pipeline.register(PipelineStage.AUDIO_READY, self._run_audio, weight=18)
        if self.transcription_service is not None and self.transcription_service.enabled():
            pipeline.register(
                PipelineStage.TRANSCRIPTION_READY,
                self.transcription_service.stage_runner(),
                weight=40,
            )
        if self.subtitle_service is not None and self.subtitle_service.enabled():
            pipeline.register(PipelineStage.SUBTITLE_READY, self.subtitle_service.stage_runner(), weight=2)
            pipeline.register(PipelineStage.SUBTITLE_VALIDATED, self.subtitle_service.validation_runner(), weight=2)
        return pipeline

    # -- stage runners ----------------------------------------------------------
    def _run_validation(self, ctx: PipelineContext) -> None:
        validate_extension(ctx.video_path)
        validate_file(ctx.video_path)
        ctx.set_progress(PipelineStage.VALIDATED, 1.0)

    def _run_metadata(self, ctx: PipelineContext) -> None:
        ctx.metadata = probe(ctx.video_path, self.ffmpeg)
        ctx.set_progress(PipelineStage.METADATA_READY, 1.0)

    def _run_thumbnail(self, ctx: PipelineContext) -> None:
        duration = ctx.metadata.duration_sec if ctx.metadata else None
        ctx.thumbnail_path = str(
            generate_thumbnail(self.ffmpeg, ctx.video_path, self.file_manager.thumbnails_dir, duration_sec=duration)
        )
        ctx.set_progress(PipelineStage.THUMBNAIL_READY, 1.0)

    def _run_audio(self, ctx: PipelineContext) -> None:
        duration = ctx.metadata.duration_sec if ctx.metadata else None
        ctx.audio_path = str(
            extract_audio(self.ffmpeg, ctx.video_path, self.file_manager.audio_dir, duration_sec=duration)
        )
        ctx.set_progress(PipelineStage.AUDIO_READY, 1.0)

    # -- plumbing -----------------------------------------------------------------
    def _on_stage_done(self, job: Job) -> None:
        self.app_state.update_job(job)

    def _cleanup_worker(self, job_id: str, worker: _PipelineWorker) -> None:
        self._workers.pop(job_id, None)
        self._contexts.pop(job_id, None)
