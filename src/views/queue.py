"""Queue page.

Phase 2: the queue shows real, processed video jobs (stage chips, progress)
plus a detail panel with video playback and metadata for the selected job.
"Load Sample Data" still provides demo rows (marked ``demo``) that the
UI-only animation advances.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QToolButton,
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
        self._last_transcript_path = ""
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

        self.cancel_button = QPushButton("Cancel Selected")
        self.cancel_button.setObjectName("GhostButton")
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.setToolTip("Cancel the selected job (takes effect between pipeline stages)")
        self.cancel_button.clicked.connect(self._cancel_selected)
        toolbar.addWidget(self.cancel_button)

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

        # -- transcript summary row -------------------------------------------
        transcript_row = QHBoxLayout()
        transcript_row.setSpacing(8)
        self.transcript_label = QLabel("No transcript yet")
        self.transcript_label.setObjectName("JobMeta")
        self.transcript_label.setWordWrap(True)
        transcript_row.addWidget(self.transcript_label, 1)
        self.open_transcript_button = QToolButton()
        self.open_transcript_button.setObjectName("LinkButton")
        self.open_transcript_button.setText("Open Transcript")
        self.open_transcript_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_transcript_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.open_transcript_button.clicked.connect(self._open_transcript)
        self.open_transcript_button.setVisible(False)
        transcript_row.addWidget(self.open_transcript_button)
        detail_layout.addLayout(transcript_row)

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
        self._update_transcript_row(job)
        self.app_state.set_status(f"Inspecting {job.filename}")

    def _update_transcript_row(self, job) -> None:
        transcript_path = job.transcript_path
        if transcript_path and Path(transcript_path).exists():
            words = job.word_count()
            language = "—"
            if job.transcript and job.transcript.get("language"):
                language = job.transcript["language"]
            self.transcript_label.setText(
                f"Transcript ready: {words} words · language {language} · {Path(transcript_path).name}"
            )
            self.open_transcript_button.setVisible(True)
            self._last_transcript_path = transcript_path
        else:
            if job.stage is ProcessStage.FAILED:
                self.transcript_label.setText(f"Transcription failed: {job.error or 'unknown error'}")
            else:
                self.transcript_label.setText(
                    "No transcript yet — transcription runs automatically after audio extraction"
                )
            self.open_transcript_button.setVisible(False)
            self._last_transcript_path = ""

    def _open_transcript(self) -> None:
        if self._last_transcript_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_transcript_path))

    def _cancel_selected(self) -> None:
        job_id = self.queue_widget.selected_job_id()
        if not job_id:
            self.app_state.set_status("Select a job to cancel it")
            return
        if self.video_service is not None:
            self.video_service.cancel_job(job_id)
            self.app_state.set_status("Cancel requested")
        else:
            self.app_state.set_status("No pipeline available to cancel")

    def _sync_detail(self) -> None:
        selected = self.queue_widget.selected_job_id()
        if selected:
            self._on_job_selected(selected)
