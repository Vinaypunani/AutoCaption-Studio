"""Queue page.

Phase 2: the queue shows real, processed video jobs (stage chips, progress)
plus a detail panel with video playback and metadata for the selected job.
"Load Sample Data" still provides demo rows (marked ``demo``) that the
UI-only animation advances.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core.app_state import AppState
from ..core.logger import get_logger
from ..models.job_model import JobStatus, ProcessStage
from ..video.preview import PreviewPanel
from ..widgets.cards import make_card
from ..widgets.queue_widget import QueueWidget
from ..widgets.video_info import VideoInfoPanel

log = get_logger("queue_view")


class QueueView(QWidget):
    """Job queue page (scrollable so small windows never clip the detail panel)."""

    def __init__(self, app_state: AppState, video_service=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app_state = app_state
        self.video_service = video_service
        self.setObjectName("QueueView")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        body = QWidget()
        outer = QVBoxLayout(body)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        title = QLabel("Queue")
        title.setObjectName("PageTitle")
        outer.addWidget(title)

        subtitle = QLabel(
            "Real video jobs appear here after processing. Select a job to preview "
            "it and inspect its metadata."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        # -- toolbar --------------------------------------------------------
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.load_button = QPushButton("Load Sample Data")
        self.load_button.setObjectName("GhostButton")
        self.load_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.load_button.clicked.connect(self._load_sample_data)
        toolbar.addWidget(self.load_button)

        self.clear_button = QPushButton("Clear Queue")
        self.clear_button.setObjectName("GhostButton")
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.clicked.connect(self.app_state.clear_jobs)
        toolbar.addWidget(self.clear_button)

        toolbar.addStretch(1)

        self.count_label = QLabel("")
        self.count_label.setObjectName("QueueCount")
        toolbar.addWidget(self.count_label)
        outer.addLayout(toolbar)

        # -- queue table -----------------------------------------------------
        self.queue_widget = QueueWidget(show_header=True)
        self.queue_widget.remove_requested.connect(self.app_state.remove_job)
        self.queue_widget.job_selected.connect(self._on_job_selected)
        outer.addWidget(make_card(None, self.queue_widget), 1)

        # -- detail panel (preview + video information) ----------------------
        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        header_label = QLabel("Job Details")
        header_label.setObjectName("CardTitle")
        header.addWidget(header_label)
        self.detail_name = QLabel("No job selected")
        self.detail_name.setObjectName("JobMeta")
        header.addWidget(self.detail_name)
        header.addStretch(1)
        detail_layout.addLayout(header)

        split = QHBoxLayout()
        split.setSpacing(14)
        self.preview = PreviewPanel()
        split.addWidget(self.preview, 3)
        self.video_info = VideoInfoPanel()
        split.addWidget(self.video_info, 4)
        detail_layout.addLayout(split)

        outer.addWidget(make_card(None, detail))

        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        self.app_state.jobs_changed.connect(self._refresh)
        self._refresh()

        # UI-only demo animation for sample (demo) jobs.
        self._demo_timer = QTimer(self)
        self._demo_timer.setInterval(250)
        self._demo_timer.timeout.connect(self._tick_demo)
        self._demo_timer.start()

    # -- actions -----------------------------------------------------------
    def _load_sample_data(self) -> None:
        self.app_state.seed_mock_jobs()
        self.app_state.set_status("Loaded sample jobs (demo data)")
        log.info("Sample jobs loaded into the queue")

    def _refresh(self) -> None:
        jobs = self.app_state.jobs()
        self.queue_widget.set_jobs(jobs)
        self.count_label.setText(f"{len(jobs)} job{'s' if len(jobs) != 1 else ''}")
        self._sync_detail()

    def _tick_demo(self) -> None:
        """Demo-only: nudge ``demo`` running jobs toward completion."""
        changed = False
        for job in self.app_state.jobs():
            if (
                job.demo
                and job.status is JobStatus.RUNNING
                and job.progress < 100.0
            ):
                job.progress = min(100.0, job.progress + 1.0)
                if job.progress >= 100.0:
                    job.status = JobStatus.COMPLETED
                    job.stage = ProcessStage.READY
                    job.eta_seconds = 0
                else:
                    job.eta_seconds = max(0, job.eta_seconds - 1)
                changed = True
        if changed:
            self.app_state.jobs_changed.emit()

    # -- selection -----------------------------------------------------------
    def _on_job_selected(self, job_id: str) -> None:
        job = next((j for j in self.app_state.jobs() if j.job_id == job_id), None)
        if job is None:
            return
        self.detail_name.setText(job.filename)
        if job.metadata is not None:
            self.video_info.set_metadata(job.metadata, job.thumbnail_path)
        else:
            self.video_info.clear()
        if job.path and Path(job.path).exists() and not job.demo:
            self.preview.set_source(job.path)
        else:
            self.preview.clear()
        self.app_state.set_status(f"Inspecting {job.filename}")

    def _sync_detail(self) -> None:
        selected = self.queue_widget.selected_job_id()
        if selected:
            self._on_job_selected(selected)
