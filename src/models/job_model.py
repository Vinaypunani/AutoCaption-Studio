"""Job data model — plain data, zero processing logic.

Phase 2 extends jobs with a processing :class:`ProcessStage`, extracted
:class:`VideoMetadata`, and the thumbnail/audio artifacts produced by the
pipeline. The pipeline itself lives in ``services/video_service.py``.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from ..core.pipeline import PipelineStage as ProcessStage  # noqa: F401 (re-exported for compatibility)
from ..video.metadata import VideoMetadata


class JobStatus(str, Enum):
    """Lifecycle state of a job (coarse)."""

    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

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
    """A single caption job (data only — processing happens in the service)."""

    filename: str
    path: str = ""
    status: JobStatus = JobStatus.WAITING
    progress: float = 0.0                # 0.0 - 100.0
    duration_sec: float = 0.0
    eta_seconds: int = 0
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)

    # -- Phase 2 ------------------------------------------------------------
    stage: ProcessStage = ProcessStage.WAITING
    metadata: Optional[VideoMetadata] = None
    thumbnail_path: str = ""
    audio_path: str = ""
    error: str = ""
    demo: bool = False  # True = sample/mock job (no real file)

    # -- Phase 3 ------------------------------------------------------------
    transcript_path: str = ""  # JSON transcript under output/transcripts/
    transcript: Optional[dict] = None  # in-memory copy (also persisted to disk)

    # -- Phase 4 ------------------------------------------------------------
    subtitle_path: str = ""  # primary format file under output/subtitles/
    subtitle_formats: dict = field(default_factory=dict)  # ext -> path
    subtitle_warnings: list = field(default_factory=list)  # validator warnings

    @classmethod
    def from_path(cls, path: str | Path, status: JobStatus = JobStatus.WAITING) -> "Job":
        """Build a waiting job from a video file path (no probing yet)."""
        path_obj = Path(path)
        return cls(filename=path_obj.name, path=str(path_obj), status=status)

    # -- display helpers ------------------------------------------------------
    def duration_display(self) -> str:
        if self.metadata and self.metadata.duration_sec:
            return format_mmss(self.metadata.duration_sec)
        return format_mmss(self.duration_sec) if self.duration_sec > 0 else "—"

    def eta_display(self) -> str:
        if self.status is JobStatus.WAITING or self.eta_seconds <= 0:
            return "—"
        return format_mmss(self.eta_seconds)

    def stage_display(self) -> str:
        return self.stage.value

    def word_count(self) -> int:
        """Total transcribed words (0 when no transcript yet)."""
        if not self.transcript:
            return 0
        return sum(
            len(segment.get("words", []))
            for segment in self.transcript.get("segments", [])
        )

    # -- serialization ---------------------------------------------------------
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
            "stage": self.stage.value,
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "thumbnail_path": self.thumbnail_path,
            "audio_path": self.audio_path,
            "transcript_path": self.transcript_path,
            "subtitle_path": self.subtitle_path,
            "subtitle_warnings": list(self.subtitle_warnings),
            "error": self.error,
            "demo": self.demo,
        }


def sample_jobs() -> list[Job]:
    """Return representative mock jobs for the UI demo (all ``demo=True``)."""
    now = datetime.datetime.now()
    return [
        Job(
            filename="interview_podcast.mp4",
            path="C:/samples/interview_podcast.mp4",
            status=JobStatus.RUNNING,
            stage=ProcessStage.EXTRACTING_AUDIO,
            progress=42.0,
            duration_sec=52 * 60,
            eta_seconds=31 * 60,
            demo=True,
            created_at=now - datetime.timedelta(minutes=3),
        ),
        Job(
            filename="tutorial_screencast.mkv",
            path="C:/samples/tutorial_screencast.mkv",
            status=JobStatus.WAITING,
            stage=ProcessStage.WAITING,
            progress=0.0,
            duration_sec=18 * 60,
            demo=True,
            created_at=now - datetime.timedelta(minutes=1),
        ),
        Job(
            filename="product_launch_video.mp4",
            path="C:/samples/product_launch_video.mp4",
            status=JobStatus.COMPLETED,
            stage=ProcessStage.READY,
            progress=100.0,
            duration_sec=2 * 60 + 5,
            demo=True,
            created_at=now - datetime.timedelta(hours=2),
        ),
        Job(
            filename="old_broadcast_capture.avi",
            path="C:/samples/old_broadcast_capture.avi",
            status=JobStatus.FAILED,
            stage=ProcessStage.FAILED,
            progress=63.0,
            duration_sec=1 * 3600 + 12 * 60 + 30,
            error="Sample failure for demo purposes",
            demo=True,
            created_at=now - datetime.timedelta(days=1),
        ),
    ]
