"""Video pipeline service.

Orchestrates the Phase 2 stages for a queued job:

    Validate → Read Metadata → Generate Thumbnail → Extract Audio → Ready

Each job runs on a dedicated :class:`QThread` worker so the UI stays
responsive; every stage update is delivered back to the main thread through
a signal and applied to :class:`AppState` (which notifies the views).
"""

from __future__ import annotations

import copy
from typing import Optional, Set

from PySide6.QtCore import QObject, QThread, Signal

from ..core.logger import get_logger
from ..core.app_state import AppState
from ..models.job_model import Job, JobStatus, ProcessStage
from ..video import FileManager, FFmpegManager
from ..video.exceptions import UnsupportedFormatError, VideoProcessingError
from ..video.extractor import extract_audio
from ..video.metadata import probe
from ..video.thumbnail import generate_thumbnail
from ..video.validator import validate_extension, validate_file

log = get_logger("video_service")

# Approximate progress weights per stage (out of 100).
_STAGE_PROGRESS = {
    ProcessStage.VALIDATING: 8,
    ProcessStage.READING_METADATA: 35,
    ProcessStage.GENERATING_THUMBNAIL: 60,
    ProcessStage.EXTRACTING_AUDIO: 90,
    ProcessStage.READY: 100,
}


class _PipelineWorker(QThread):
    """Runs the media pipeline for a single job snapshot."""

    stage_done = Signal(object)  # Job

    def __init__(
        self,
        job: Job,
        ffmpeg: FFmpegManager,
        file_manager: FileManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.job = job
        self.ffmpeg = ffmpeg
        self.file_manager = file_manager

    def run(self) -> None:  # noqa: C901 - linear pipeline, flat by design
        job = self.job
        try:
            self._emit(job, ProcessStage.VALIDATING, _STAGE_PROGRESS[ProcessStage.VALIDATING])
            validate_extension(job.path)
            validate_file(job.path)

            self._emit(job, ProcessStage.READING_METADATA, _STAGE_PROGRESS[ProcessStage.READING_METADATA])
            job.metadata = probe(job.path, self.ffmpeg)
            job.duration_sec = job.metadata.duration_sec

            self._emit(job, ProcessStage.GENERATING_THUMBNAIL, _STAGE_PROGRESS[ProcessStage.GENERATING_THUMBNAIL])
            thumbnail = generate_thumbnail(
                self.ffmpeg, job.path, self.file_manager.thumbnails_dir,
                duration_sec=job.metadata.duration_sec,
            )
            job.thumbnail_path = str(thumbnail)

            self._emit(job, ProcessStage.EXTRACTING_AUDIO, _STAGE_PROGRESS[ProcessStage.EXTRACTING_AUDIO])
            audio = extract_audio(
                self.ffmpeg, job.path, self.file_manager.audio_dir,
                duration_sec=job.metadata.duration_sec,
            )
            job.audio_path = str(audio)

            job.status = JobStatus.COMPLETED
            job.stage = ProcessStage.READY
            job.progress = _STAGE_PROGRESS[ProcessStage.READY]
            job.error = ""
            log.info("Pipeline finished: %s", job.filename)
        except UnsupportedFormatError as exc:
            self._fail(job, exc)
        except VideoProcessingError as exc:
            self._fail(job, exc)
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("Unexpected pipeline error for %s", job.filename)
            self._fail(job, exc)
        finally:
            self.stage_done.emit(job)

    # -- helpers ---------------------------------------------------------------
    def _emit(self, job: Job, stage: ProcessStage, progress: float) -> None:
        job.status = JobStatus.RUNNING
        job.stage = stage
        job.progress = progress
        log.info("Stage %s: %s", stage.value, job.filename)
        self.stage_done.emit(job)

    def _fail(self, job: Job, exc: Exception) -> None:
        job.status = JobStatus.FAILED
        job.stage = ProcessStage.FAILED
        job.error = str(exc)
        log.error("Job failed (%s): %s", job.filename, exc)


class VideoService(QObject):
    """Main-thread owner of pipeline workers."""

    def __init__(
        self,
        app_state: AppState,
        ffmpeg: Optional[FFmpegManager] = None,
        file_manager: Optional[FileManager] = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_state = app_state
        self.ffmpeg = ffmpeg or FFmpegManager()
        self.file_manager = file_manager or FileManager()
        self._workers: Set[_PipelineWorker] = set()

        if not self.ffmpeg.available():
            log.warning("FFmpeg unavailable — pipeline is disabled")

    # -- API -----------------------------------------------------------------
    def can_process(self) -> bool:
        """True when ffmpeg is available so jobs can be processed."""
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
        # The worker runs on its own *copy*; AppState.update_job (main thread)
        # is the only writer of the shared state, so views never observe a
        # half-mutated job.
        worker = _PipelineWorker(copy.copy(job), self.ffmpeg, self.file_manager)
        worker.stage_done.connect(self._on_stage_done)
        worker.finished.connect(lambda w=worker: self._workers.discard(w))
        self._workers.add(worker)
        log.info("Pipeline started for job %s", job_id)
        worker.start()

    def _on_stage_done(self, job: Job) -> None:
        """Apply a worker's snapshot to the shared state (main thread)."""
        self.app_state.update_job(job)

    def shutdown(self, timeout_ms: int = 5000) -> None:
        """Wait for in-flight workers so the app can exit cleanly."""
        for worker in list(self._workers):
            if worker.isRunning():
                worker.wait(timeout_ms)
            self._workers.discard(worker)
