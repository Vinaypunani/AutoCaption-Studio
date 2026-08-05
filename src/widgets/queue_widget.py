"""Reusable job queue widget.

Renders the job queue as a compact list (or table-like grid with a header)
and updates rows incrementally so progress changes never rebuild the UI.
Used both on the Home page (mini preview) and the Queue page (full table).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..models.job_model import Job, JobStatus
from .progress_widget import ProgressWidget

_COL_FILE = 0
_COL_STATUS = 1
_COL_PROGRESS = 2
_COL_ETA = 3
_COL_REMOVE = 4

_STATUS_COLORS: dict[JobStatus, str] = {
    JobStatus.WAITING: "waiting",
    JobStatus.RUNNING: "running",
    JobStatus.COMPLETED: "completed",
    JobStatus.FAILED: "failed",
}


class JobRow(QFrame):
    """One row of the queue: file, status chip, progress, ETA, remove."""

    remove_requested = Signal(str)  # job_id

    def __init__(self, job: Job, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("JobRow")
        self.setFixedHeight(64)
        self._job = job

        grid = QGridLayout(self)
        grid.setContentsMargins(14, 8, 10, 8)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(0)
        grid.setColumnStretch(_COL_FILE, 1)
        grid.setColumnMinimumWidth(_COL_STATUS, 84)
        grid.setColumnMinimumWidth(_COL_PROGRESS, 140)
        grid.setColumnMinimumWidth(_COL_ETA, 64)
        grid.setColumnMinimumWidth(_COL_REMOVE, 28)

        self.name_label = QLabel()
        self.name_label.setObjectName("JobName")
        self.name_label.setToolTip("")
        grid.addWidget(self.name_label, 0, _COL_FILE)

        self.meta_label = QLabel()
        self.meta_label.setObjectName("JobMeta")
        grid.addWidget(self.meta_label, 1, _COL_FILE)

        self.chip = QLabel()
        self.chip.setObjectName("StatusChip")
        self.chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chip.setFixedHeight(22)
        grid.addWidget(self.chip, 0, _COL_STATUS, 2, 1)

        self.progress = ProgressWidget(height=6)
        grid.addWidget(self.progress, 0, _COL_PROGRESS, 2, 1)

        self.eta_label = QLabel()
        self.eta_label.setObjectName("JobEta")
        self.eta_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(self.eta_label, 0, _COL_ETA, 2, 1)

        remove = QToolButton()
        remove.setObjectName("RemoveButton")
        remove.setText("✕")
        remove.setToolTip("Remove job")
        remove.setCursor(Qt.CursorShape.PointingHandCursor)
        remove.setFixedSize(24, 24)
        remove.clicked.connect(lambda: self.remove_requested.emit(self._job.job_id))
        grid.addWidget(remove, 0, _COL_REMOVE, 2, 1)

        self.update_job(job)

    # -- updates -----------------------------------------------------------
    def update_job(self, job: Job) -> None:
        """Refresh the row from a (possibly mutated) job."""
        self._job = job
        self.name_label.setText(self._elide(job.filename, 280))
        self.name_label.setToolTip(f"{job.filename}\n{job.path}" if job.path else job.filename)
        self.meta_label.setText(job.duration_display())
        self.chip.setText(job.status.display)
        self.chip.setProperty("status", _STATUS_COLORS.get(job.status, "waiting"))
        self.chip.style().unpolish(self.chip)
        self.chip.style().polish(self.chip)
        self.progress.set_value(job.progress)
        self.progress.set_indeterminate(job.status is JobStatus.RUNNING)
        if job.status is JobStatus.RUNNING:
            self.progress.start_animation()
        else:
            self.progress.stop_animation()
        self.eta_label.setText(job.eta_display())

    def job(self) -> Job:
        return self._job

    def _elide(self, text: str, max_width: int) -> str:
        """Elide long names in the middle; the full name stays in the tooltip."""
        metrics = self.fontMetrics()
        if metrics.horizontalAdvance(text) <= max_width:
            return text
        return metrics.elidedText(text, Qt.TextElideMode.ElideMiddle, max_width)


class QueueWidget(QWidget):
    """Scrollable job queue with an optional table-style header."""

    remove_requested = Signal(str)  # job_id

    def __init__(self, show_header: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: dict[str, JobRow] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        if show_header:
            outer.addWidget(self._build_header())

        self._empty_label = QLabel("No Jobs Yet\nDrop a video or load sample data to get started")
        self._empty_label.setObjectName("EmptyState")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._empty_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        self._list_layout = QVBoxLayout(container)
        self._list_layout.setContentsMargins(4, 8, 4, 8)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch(1)

        scroll.setWidget(container)
        outer.addWidget(scroll, 1)

    # -- building blocks ---------------------------------------------------
    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("QueueHeader")
        grid = QGridLayout(header)
        grid.setContentsMargins(14, 2, 10, 2)
        grid.setHorizontalSpacing(12)
        grid.setColumnStretch(_COL_FILE, 1)
        grid.setColumnMinimumWidth(_COL_STATUS, 84)
        grid.setColumnMinimumWidth(_COL_PROGRESS, 140)
        grid.setColumnMinimumWidth(_COL_ETA, 64)
        grid.setColumnMinimumWidth(_COL_REMOVE, 28)
        for col, text in [
            (_COL_FILE, "File"),
            (_COL_STATUS, "Status"),
            (_COL_PROGRESS, "Progress"),
            (_COL_ETA, "ETA"),
            (_COL_REMOVE, ""),
        ]:
            label = QLabel(text)
            label.setObjectName("QueueHeaderLabel")
            if col == _COL_STATUS or col == _COL_ETA:
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(label, 0, col)
        return header

    # -- API ---------------------------------------------------------------
    def set_jobs(self, jobs: list[Job]) -> None:
        """Reconcile the displayed rows with ``jobs`` (incremental update)."""
        ids = {job.job_id for job in jobs}
        for job in jobs:
            row = self._rows.get(job.job_id)
            if row is not None:
                row.update_job(job)
            else:
                self._add_row(job)

        stale = [job_id for job_id in self._rows if job_id not in ids]
        for job_id in stale:
            row = self._rows.pop(job_id)
            self._list_layout.removeWidget(row)
            row.deleteLater()

        self._empty_label.setVisible(not jobs)

    def job_count(self) -> int:
        return len(self._rows)

    def _add_row(self, job: Job) -> None:
        row = JobRow(job)
        row.remove_requested.connect(self.remove_requested)
        self._rows[job.job_id] = row
        self._list_layout.insertWidget(self._list_layout.count() - 1, row)
