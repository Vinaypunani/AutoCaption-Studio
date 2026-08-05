"""Job model: construction, formatting and sample data."""

from src.models.job_model import Job, JobStatus, ProcessStage, format_mmss, sample_jobs


def test_format_mmss():
    assert format_mmss(65) == "01:05"
    assert format_mmss(3725) == "1:02:05"
    assert format_mmss(0) == "00:00"


def test_job_from_path():
    from pathlib import Path

    source = "C:/videos/clip.mp4"
    job = Job.from_path(source)
    assert job.filename == "clip.mp4"
    # Path normalises separators to the host platform (\ on Windows).
    assert job.path == str(Path(source))
    assert job.status is JobStatus.WAITING
    assert job.progress == 0.0
    assert job.job_id  # generated


def test_sample_jobs_are_valid_and_unique():
    jobs = sample_jobs()
    assert len(jobs) == 4
    assert len({job.job_id for job in jobs}) == len(jobs)  # unique ids
    for job in jobs:
        assert 0.0 <= job.progress <= 100.0
        assert job.status in JobStatus
        assert job.filename


def test_display_helpers():
    waiting = Job(filename="a.mp4", status=JobStatus.WAITING, eta_seconds=120)
    assert waiting.eta_display() == "—"  # waiting jobs show no ETA

    running = Job(filename="b.mp4", status=JobStatus.RUNNING, eta_seconds=65)
    assert running.eta_display() == "01:05"

    completed = Job(filename="c.mp4", status=JobStatus.COMPLETED, duration_sec=125)
    assert completed.duration_display() == "02:05"
    assert completed.eta_display() == "—"


def test_job_serialization_roundtrip():
    job = Job(filename="clip.mp4", path="C:/videos/clip.mp4", status=JobStatus.COMPLETED, progress=100.0)
    data = job.to_dict()
    assert data["filename"] == "clip.mp4"
    assert data["status"] == "completed"
    assert data["progress"] == 100.0
    assert data["stage"] == "Waiting"
    assert data["metadata"] is None
    assert data["demo"] is False
    assert "created_at" in data


def test_job_phase2_defaults():
    job = Job(filename="clip.mp4")
    assert job.stage is ProcessStage.WAITING
    assert job.thumbnail_path == ""
    assert job.audio_path == ""
    assert job.error == ""
    assert job.demo is False


def test_sample_jobs_are_demo():
    assert all(job.demo for job in sample_jobs())


def test_job_serializes_metadata():
    from src.video.metadata import VideoMetadata

    meta = VideoMetadata(filename="clip.mp4", extension=".mp4", path="C:/clip.mp4", duration_sec=12.5)
    job = Job(filename="clip.mp4", path="C:/clip.mp4", stage=ProcessStage.COMPLETED, metadata=meta, progress=100.0)
    data = job.to_dict()
    assert data["stage"] == "Completed"
    assert data["metadata"]["duration_sec"] == 12.5


def test_job_phase3_defaults():
    job = Job(filename="clip.mp4")
    assert job.transcript_path == ""
    assert job.transcript is None
    assert job.word_count() == 0


def test_job_word_count_from_transcript():
    job = Job(filename="clip.mp4")
    job.transcript = {
        "segments": [
            {"words": [{"word": "Hello"}, {"word": "world"}]},
            {"words": [{"word": "!"}]},
        ]
    }
    assert job.word_count() == 3


def test_job_duration_uses_metadata():
    from src.video.metadata import VideoMetadata

    meta = VideoMetadata(filename="clip.mp4", extension=".mp4", path="C:/clip.mp4", duration_sec=125)
    job = Job(filename="clip.mp4", path="C:/clip.mp4", metadata=meta)
    assert job.duration_display() == "02:05"
