"""Job data model — plain data, zero processing logic.

Later phases attach real pipeline state (transcription, subtitle files,
FFmpeg progress) to this same model.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class JobStatus(str, Enum):
    """Lifecycle states of a caption job."""

    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def display(self) -> str:
        return self.value.title()


def format_mmss(total_seconds: float | int) -> str:
    """Format a duration as ``H:MM:SS`` or ``MM:SS``."""
    total = int(total_seconds)
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


@dataclass
class Job:
    """A single queued caption job (data only — no processing)."""

    filename: str
    path: str = ""
    status: JobStatus = JobStatus.WAITING
    progress: float = 0.0                # 0.0 - 100.0
    duration_sec: float = 0.0
    eta_seconds: int = 0
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)

    @classmethod
    def from_path(cls, path: str | Path, status: JobStatus = JobStatus.WAITING) -> "Job":
        """Build a waiting job from a video file path (no metadata probing yet)."""
        path_obj = Path(path)
        return cls(filename=path_obj.name, path=str(path_obj), status=status)

    def duration_display(self) -> str:
        return format_mmss(self.duration_sec) if self.duration_sec > 0 else "—"

    def eta_display(self) -> str:
        if self.status is JobStatus.WAITING or self.eta_seconds <= 0:
            return "—"
        return format_mmss(self.eta_seconds)

    def to_dict(self) -> dict:
        """Serialize for future persistence (e.g. resuming a session)."""
        return {
            "job_id": self.job_id,
            "filename": self.filename,
            "path": self.path,
            "status": self.status.value,
            "progress": self.progress,
            "duration_sec": self.duration_sec,
            "eta_seconds": self.eta_seconds,
            "created_at": self.created_at.isoformat(),
        }


def sample_jobs() -> list[Job]:
    """Return representative mock jobs for the Phase 1 queue demo."""
    now = datetime.datetime.now()
    return [
        Job(
            filename="interview_podcast.mp4",
            path="C:/samples/interview_podcast.mp4",
            status=JobStatus.RUNNING,
            progress=42.0,
            duration_sec=52 * 60,
            eta_seconds=31 * 60,
            created_at=now - datetime.timedelta(minutes=3),
        ),
        Job(
            filename="tutorial_screencast.mkv",
            path="C:/samples/tutorial_screencast.mkv",
            status=JobStatus.WAITING,
            progress=0.0,
            duration_sec=18 * 60,
            eta_seconds=0,
            created_at=now - datetime.timedelta(minutes=1),
        ),
        Job(
            filename="product_launch_video.mp4",
            path="C:/samples/product_launch_video.mp4",
            status=JobStatus.COMPLETED,
            progress=100.0,
            duration_sec=2 * 60 + 5,
            eta_seconds=0,
            created_at=now - datetime.timedelta(hours=2),
        ),
        Job(
            filename="old_broadcast_capture.avi",
            path="C:/samples/old_broadcast_capture.avi",
            status=JobStatus.FAILED,
            progress=63.0,
            duration_sec=1 * 3600 + 12 * 60 + 30,
            eta_seconds=0,
            created_at=now - datetime.timedelta(days=1),
        ),
    ]
