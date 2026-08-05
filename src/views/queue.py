"""Queue page.

Full job queue table. Phase 1 uses *mock data only*; the demo timer that
advances running-job progress is purely a UI animation — no processing.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.app_state import AppState
from ..core.logger import get_logger
from ..models.job_model import JobStatus
from ..widgets.cards import make_card
from ..widgets.queue_widget import QueueWidget

log = get_logger("queue_view")


class QueueView(QWidget):
    """Job queue page."""

    def __init__(self, app_state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app_state = app_state
        self.setObjectName("QueueView")
        self._seeded = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        title = QLabel("Queue")
        title.setObjectName("PageTitle")
        outer.addWidget(title)

        subtitle = QLabel(
            "Caption jobs appear here. Phase 1 shows sample data only — "
            "real processing hooks arrive in later phases."
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
        outer.addWidget(make_card(None, self.queue_widget), 1)

        self.app_state.jobs_changed.connect(self._refresh)
        self._refresh()

        # UI-only demo: advance running jobs so the progress animation is
        # visible. Runs only while the Queue page is on screen.
        self._demo_timer = QTimer(self)
        self._demo_timer.setInterval(250)
        self._demo_timer.timeout.connect(self._tick_progress)

    # -- lifecycle ---------------------------------------------------------
    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        if not self._seeded:
            self._seeded = True
            self._load_sample_data()
        self._demo_timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().hideEvent(event)
        self._demo_timer.stop()

    # -- actions -----------------------------------------------------------
    def _load_sample_data(self) -> None:
        self.app_state.seed_mock_jobs()
        self.app_state.set_status("Loaded sample jobs (mock data, Phase 1)")
        log.info("Sample jobs loaded into the queue")

    def _refresh(self) -> None:
        jobs = self.app_state.jobs()
        self.queue_widget.set_jobs(jobs)
        self.count_label.setText(f"{len(jobs)} job{'s' if len(jobs) != 1 else ''}")

    def _tick_progress(self) -> None:
        """Demo-only: nudge running jobs toward completion (no real work)."""
        changed = False
        for job in self.app_state.jobs():
            if job.status is JobStatus.RUNNING and job.progress < 100.0:
                job.progress = min(100.0, job.progress + 1.0)
                if job.progress >= 100.0:
                    job.status = JobStatus.COMPLETED
                    job.eta_seconds = 0
                else:
                    job.eta_seconds = max(0, job.eta_seconds - 1)
                changed = True
        if changed:
            self.app_state.jobs_changed.emit()
