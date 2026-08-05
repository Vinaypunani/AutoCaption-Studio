"""VideoService pipeline: end-to-end processing of a real video."""

import time
from pathlib import Path

import pytest

from src.models.job_model import Job, JobStatus, ProcessStage
from src.services.video_service import VideoService


def _wait_for(predicate, timeout: float = 30.0) -> None:
    """Pump the Qt event loop until ``predicate()`` is true."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        if app is not None:
            app.processEvents()
        time.sleep(0.02)
    raise AssertionError("timed out waiting for condition")


_TERMINAL = (JobStatus.COMPLETED, JobStatus.FAILED)


def _find_job(app_state, job_id):
    return next(j for j in app_state.jobs() if j.job_id == job_id)


def test_pipeline_processes_real_job(qapp, config, app_state, ffmpeg, file_manager, sample_video):
    service = VideoService(app_state, ffmpeg, file_manager)
    job = Job.from_path(sample_video)
    app_state.add_job(job)

    service.process_job(job.job_id)
    _wait_for(lambda: _find_job(app_state, job.job_id).status in _TERMINAL)

    updated = _find_job(app_state, job.job_id)
    assert updated.status is JobStatus.COMPLETED
    assert updated.stage is ProcessStage.READY
    assert updated.progress == 100.0
    assert updated.metadata is not None
    assert updated.metadata.duration_sec > 0
    assert updated.thumbnail_path and Path(updated.thumbnail_path).exists()
    assert updated.audio_path and Path(updated.audio_path).exists()


def test_pipeline_reports_intermediate_stages(qapp, config, app_state, ffmpeg, file_manager, sample_video):
    """Jobs must pass through intermediate stages before reaching Ready."""
    service = VideoService(app_state, ffmpeg, file_manager)
    job = Job.from_path(sample_video)
    app_state.add_job(job)

    observed: list[str] = []

    def _on_change() -> None:
        observed.append(_find_job(app_state, job.job_id).stage.value)

    app_state.jobs_changed.connect(_on_change)

    service.process_job(job.job_id)
    # Wait for the final stage to be *delivered* (not just mutated on the
    # shared job object) so we can assert on the observed sequence.
    _wait_for(lambda: "Completed" in observed)
    assert any(
        stage in observed
        for stage in ("Validated", "Metadata Ready", "Thumbnail Ready", "Audio Ready")
    )


def test_pipeline_fails_gracefully_on_corrupt(qapp, config, app_state, ffmpeg, file_manager, corrupt_video):
    service = VideoService(app_state, ffmpeg, file_manager)
    job = Job.from_path(corrupt_video)
    app_state.add_job(job)

    service.process_job(job.job_id)
    _wait_for(lambda: _find_job(app_state, job.job_id).status is JobStatus.FAILED)

    updated = _find_job(app_state, job.job_id)
    assert updated.stage is ProcessStage.FAILED
    assert updated.error, "failed job should carry an error message"


def test_pipeline_without_ffmpeg_is_noop(qapp, config, app_state, file_manager):
    from src.video import FFmpegManager

    no_ffmpeg = FFmpegManager(ffmpeg_path="C:/definitely/not/ffmpeg.exe")
    service = VideoService(app_state, no_ffmpeg, file_manager)
    assert service.can_process() is False

    job = Job.from_path("C:/videos/some.mp4")
    app_state.add_job(job)
    service.process_job(job.job_id)
    time.sleep(0.05)
    assert _find_job(app_state, job.job_id).status is JobStatus.WAITING


def test_demo_jobs_are_not_processed(qapp, config, app_state, ffmpeg, file_manager, sample_video):
    service = VideoService(app_state, ffmpeg, file_manager)
    job = Job.from_path(sample_video)
    job.demo = True
    app_state.add_job(job)

    service.process_job(job.job_id)
    time.sleep(0.05)
    assert _find_job(app_state, job.job_id).status is JobStatus.WAITING
