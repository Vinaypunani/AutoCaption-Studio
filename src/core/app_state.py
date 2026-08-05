"""Shared application state — the light "view-model" of the MVVM-ish design.

Views never touch the config file or the job list directly; they interact
with this QObject and react to its signals. Later phases can swap the mock
jobs and add real processing services behind the same interface.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from ..core.config_manager import ConfigManager
from ..core.constants import MAX_RECENT_FILES
from ..core.logger import get_logger
from ..models.job_model import Job, sample_jobs

log = get_logger("state")


class AppState(QObject):
    """Observable, shared application state."""

    theme_changed = Signal(str)                 # new theme key
    jobs_changed = Signal()                     # job list mutated
    recent_files_changed = Signal(list)         # new recent-file list
    status_message = Signal(str)                # transient status-bar text

    def __init__(self, config: ConfigManager, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self._theme: str = str(config.get("theme", "dark"))
        self._jobs: list[Job] = []
        self._recent_files: list[str] = [p for p in config.get("recent_files", []) if isinstance(p, str)]

    # -- theme -------------------------------------------------------------
    def theme(self) -> str:
        return self._theme

    def set_theme(self, name: str, persist: bool = True) -> None:
        """Switch the active theme; optionally persist it immediately."""
        if name == self._theme:
            return
        self._theme = name
        if persist:
            self.config.set("theme", name)
            self.config.save()
        log.info("Theme set to %s", name)
        self.theme_changed.emit(name)

    # -- job queue ---------------------------------------------------------
    def jobs(self) -> list[Job]:
        return list(self._jobs)

    def add_job(self, job: Job) -> None:
        self._jobs.append(job)
        log.info("Job added to queue: %s (%s)", job.filename, job.job_id)
        self.jobs_changed.emit()

    def remove_job(self, job_id: str) -> None:
        before = len(self._jobs)
        self._jobs = [j for j in self._jobs if j.job_id != job_id]
        if len(self._jobs) != before:
            log.info("Job removed from queue: %s", job_id)
            self.jobs_changed.emit()

    def update_job(self, job: Job) -> None:
        """Replace an existing job (by id) with an updated copy."""
        for i, existing in enumerate(self._jobs):
            if existing.job_id == job.job_id:
                self._jobs[i] = job
                self.jobs_changed.emit()
                return

    def clear_jobs(self) -> None:
        if self._jobs:
            self._jobs = []
            log.info("Job queue cleared")
            self.jobs_changed.emit()

    def seed_mock_jobs(self) -> None:
        """Populate the queue with sample data (Phase 1: UI demo only)."""
        self._jobs = sample_jobs()
        log.info("Queue seeded with %d mock jobs", len(self._jobs))
        self.jobs_changed.emit()

    # -- recent files ------------------------------------------------------
    def recent_files(self) -> list[str]:
        return list(self._recent_files)

    def add_recent_file(self, path: str | Path, persist: bool = True) -> None:
        text = str(path)
        if text in self._recent_files:
            self._recent_files.remove(text)
        self._recent_files.insert(0, text)
        self._recent_files = self._recent_files[:MAX_RECENT_FILES]
        if persist:
            self.config.set("recent_files", self._recent_files)
            self.config.save()
        self.recent_files_changed.emit(list(self._recent_files))

    def clear_recent_files(self, persist: bool = True) -> None:
        self._recent_files = []
        if persist:
            self.config.set("recent_files", [])
            self.config.save()
        self.recent_files_changed.emit([])

    # -- status ------------------------------------------------------------
    def set_status(self, message: str) -> None:
        self.status_message.emit(message)
