"""Reusable job queue widget.

Renders the job queue as a table-like list with stage chips, progress and
ETA, updates rows incrementally, and supports selecting a row so detail
panels (video info + preview) can follow the selection.
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

from ..models.job_model import Job, JobStatus, ProcessStage
from .progress_widget import ProgressWidget

_COL_FILE = 0
_COL_STATUS = 1
_COL_PROGRESS = 2
_COL_ETA = 3
_COL_REMOVE = 4

# Stage -> QSS chip colour key.
_STAGE_CHIP_COLOR: dict[ProcessStage, str] = {
    ProcessStage.WAITING: "waiting",
    ProcessStage.VALIDATING: "running",
    ProcessStage.READING_METADATA: "running",
    ProcessStage.GENERATING_THUMBNAIL: "running",
    ProcessStage.EXTRACTING_AUDIO: "running",
    ProcessStage.TRANSCRIBING: "running",
    ProcessStage.TRANSCRIPTION_READY: "completed",
    ProcessStage.SUBTITLE_READY: "completed",
    ProcessStage.RENDER_READY: "completed",
    ProcessStage.READY: "completed",
    ProcessStage.CANCELLED: "cancelled",
    ProcessStage.FAILED: "failed",
}

_WORK_STAGES = {
    ProcessStage.VALIDATING,
    ProcessStage.READING_METADATA,
    ProcessStage.GENERATING_THUMBNAIL,
    ProcessStage.EXTRACTING_AUDIO,
    ProcessStage.TRANSCRIBING,
}


class JobRow(QFrame):
    """One queue row: file, stage chip, progress, ETA, remove; clickable."""

    remove_requested = Signal(str)   # job_id
    job_selected = Signal(str)       # job_id

    def __init__(self, job: Job, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("JobRow")
        self.setFixedHeight(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._job = job
        self._selected = False

        grid = QGridLayout(self)
        grid.setContentsMargins(14, 8, 10, 8)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(0)
        grid.setColumnStretch(_COL_FILE, 1)
        grid.setColumnMinimumWidth(_COL_STATUS, 96)
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
        self.name_label.setText(self._elide(job.filename, 260))
        tooltip = f"{job.filename}\n{job.path}" if job.path else job.filename
        if job.error:
            tooltip += f"\n⚠ {job.error}"
        self.name_label.setToolTip(tooltip)
        self.meta_label.setText(job.duration_display())

        chip_text = job.stage_display()
        self.chip.setText(chip_text)
        self.chip.setProperty("status", _STAGE_CHIP_COLOR.get(job.stage, "waiting"))
        self.chip.style().unpolish(self.chip)
        self.chip.style().polish(self.chip)

        self.progress.set_value(job.progress)
        is_working = job.stage in _WORK_STAGES and job.status is JobStatus.RUNNING
        self.progress.set_indeterminate(is_working)
        if is_working:
            self.progress.start_animation()
        else:
            self.progress.stop_animation()

        self.eta_label.setText(job.eta_display())

    def job(self) -> Job:
        return self._job

    def set_selected(self, selected: bool) -> None:
        if selected != self._selected:
            self._selected = selected
            self.setProperty("selected", selected)
            self.style().unpolish(self)
            self.style().polish(self)

    def is_selected(self) -> bool:
        return self._selected

    # -- interaction --------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.MouseButton.LeftButton:
            self.job_selected.emit(self._job.job_id)
            event.accept()
            return
        super().mousePressEvent(event)

    # -- helpers ---------------------------------------------------------------
    def _elide(self, text: str, max_width: int) -> str:
        metrics = self.fontMetrics()
        if metrics.horizontalAdvance(text) <= max_width:
            return text
        return metrics.elidedText(text, Qt.TextElideMode.ElideMiddle, max_width)


class QueueWidget(QWidget):
    """Scrollable job queue with an optional table-style header."""

    remove_requested = Signal(str)  # job_id
    job_selected = Signal(str)      # job_id

    def __init__(self, show_header: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: dict[str, JobRow] = {}
        self._selected_id: str = ""

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
        grid.setColumnMinimumWidth(_COL_STATUS, 96)
        grid.setColumnMinimumWidth(_COL_PROGRESS, 140)
        grid.setColumnMinimumWidth(_COL_ETA, 64)
        grid.setColumnMinimumWidth(_COL_REMOVE, 28)
        for col, text in [
            (_COL_FILE, "File"),
            (_COL_STATUS, "Stage"),
            (_COL_PROGRESS, "Progress"),
            (_COL_ETA, "ETA"),
            (_COL_REMOVE, ""),
        ]:
            label = QLabel(text)
            label.setObjectName("QueueHeaderLabel")
            if col in (_COL_STATUS, _COL_ETA):
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

        if self._selected_id not in ids:
            self._selected_id = ""
        for row in self._rows.values():
            row.set_selected(row.job().job_id == self._selected_id)

        self._empty_label.setVisible(not jobs)

    def selected_job_id(self) -> str:
        return self._selected_id

    def job_count(self) -> int:
        return len(self._rows)

    def _add_row(self, job: Job) -> None:
        row = JobRow(job)
        row.remove_requested.connect(self.remove_requested)
        row.job_selected.connect(self._on_row_selected)
        self._rows[job.job_id] = row
        self._list_layout.insertWidget(self._list_layout.count() - 1, row)

    def _on_row_selected(self, job_id: str) -> None:
        self._selected_id = job_id
        for row in self._rows.values():
            row.set_selected(row.job().job_id == job_id)
        self.job_selected.emit(job_id)
