"""Home page.

Composition of the Phase 1 dashboard: drop zone, current project,
recent files, quick settings and a preview of the job queue. Dropped
files are queued as *waiting* jobs — nothing is processed.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core.app_state import AppState
from ..core.config_manager import ConfigManager
from ..core.constants import SUPPORTED_VIDEO_FILTER
from ..core.logger import get_logger
from ..models.job_model import Job
from ..services.theme_service import ThemeService
from ..widgets.cards import make_card
from ..widgets.drop_zone import DropZone
from ..widgets.queue_widget import QueueWidget

log = get_logger("home")


class HomeView(QWidget):
    """Dashboard page."""

    navigate_requested = Signal(str)  # e.g. "queue"

    def __init__(
        self,
        app_state: AppState,
        theme_service: ThemeService,
        config: ConfigManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_state = app_state
        self.theme_service = theme_service
        self.config = config
        self.setObjectName("HomeView")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        title = QLabel("Home")
        title.setObjectName("PageTitle")
        outer.addWidget(title)

        subtitle = QLabel(
            "Drop a video to queue it. Caption generation arrives in a later phase — "
            "this build is the application shell only."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        # -- drop zone -----------------------------------------------------
        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self._on_files_dropped)
        self.drop_zone.browse_clicked.connect(self._browse_files)
        outer.addWidget(self.drop_zone)

        # -- current project ------------------------------------------------
        project_row = QWidget()
        project_layout = QHBoxLayout(project_row)
        project_layout.setContentsMargins(0, 0, 0, 0)
        project_layout.setSpacing(12)
        project_name = QLabel("🎬  Untitled Project")
        project_name.setObjectName("ProjectName")
        project_meta = QLabel("No video selected yet")
        project_meta.setObjectName("ProjectMeta")
        project_layout.addWidget(project_name)
        project_layout.addWidget(project_meta)
        project_layout.addStretch(1)
        outer.addWidget(make_card("Current Project", project_row))

        # -- recent files + quick settings ----------------------------------
        side_row = QHBoxLayout()
        side_row.setSpacing(14)

        recent_widget = self._build_recent_files()
        side_row.addWidget(recent_widget, 1)

        quick_widget = self._build_quick_settings()
        side_row.addWidget(quick_widget, 1)

        outer.addLayout(side_row)

        # -- recent jobs preview --------------------------------------------
        self.mini_queue = QueueWidget(show_header=False)
        self.mini_queue.setFixedHeight(180)
        self.mini_queue.remove_requested.connect(self.app_state.remove_job)

        jobs_card = QWidget()
        jobs_layout = QVBoxLayout(jobs_card)
        jobs_layout.setContentsMargins(0, 0, 0, 0)
        jobs_layout.setSpacing(4)
        jobs_layout.addWidget(self.mini_queue)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addStretch(1)
        view_all = QToolButton()
        view_all.setObjectName("LinkButton")
        view_all.setText("View All →")
        view_all.setCursor(Qt.CursorShape.PointingHandCursor)
        view_all.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        view_all.clicked.connect(lambda: self.navigate_requested.emit("queue"))
        footer.addWidget(view_all)
        jobs_layout.addLayout(footer)

        outer.addWidget(make_card("Recent Jobs", jobs_card))
        outer.addStretch(1)

        self._connect_state()

    # -- sub-builders ------------------------------------------------------
    def _build_recent_files(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.recent_list = QListWidget()
        self.recent_list.setObjectName("RecentList")
        self.recent_list.setFixedHeight(120)
        self.recent_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.recent_list)

        clear = QToolButton()
        clear.setObjectName("LinkButton")
        clear.setText("Clear")
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        clear.clicked.connect(self.app_state.clear_recent_files)
        layout.addWidget(clear, 0, Qt.AlignmentFlag.AlignRight)

        self._refresh_recent_files()
        return container

    def _build_quick_settings(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName("SettingsCombo")
        for theme in self.theme_service.available_themes():
            self.theme_combo.addItem(self.theme_service.display_name(theme), theme)
        self.theme_combo.setCurrentIndex(
            max(0, self.theme_combo.findData(self.app_state.theme()))
        )
        self.theme_combo.currentIndexChanged.connect(self._on_quick_theme)
        layout.addWidget(self._labeled("Theme", self.theme_combo))

        self.gpu_check = QCheckBox("Use GPU acceleration")
        self.gpu_check.setChecked(bool(self.config.get("gpu", True)))
        self.gpu_check.setToolTip("Reserved for later phases")
        self.gpu_check.toggled.connect(lambda checked: self._save_quick("gpu", checked))
        layout.addWidget(self.gpu_check)

        self.autosave_check = QCheckBox("Autosave projects")
        self.autosave_check.setChecked(bool(self.config.get("autosave", True)))
        self.autosave_check.toggled.connect(lambda checked: self._save_quick("autosave", checked))
        layout.addWidget(self.autosave_check)

        layout.addStretch(1)
        return container

    @staticmethod
    def _labeled(text: str, widget: QWidget) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        layout.addWidget(label)
        layout.addWidget(widget)
        return row

    # -- state wiring ------------------------------------------------------
    def _connect_state(self) -> None:
        self.app_state.recent_files_changed.connect(lambda _files: self._refresh_recent_files())
        self.app_state.jobs_changed.connect(self._refresh_jobs)
        self.app_state.theme_changed.connect(self._sync_theme_combo)
        self._refresh_jobs()

    def _refresh_recent_files(self) -> None:
        self.recent_list.clear()
        for path in self.app_state.recent_files():
            name = Path(path).name or path
            self.recent_list.addItem(f"🎞️  {name}")
            item = self.recent_list.item(self.recent_list.count() - 1)
            item.setToolTip(path)

    def _refresh_jobs(self) -> None:
        self.mini_queue.set_jobs(self.app_state.jobs())

    def _sync_theme_combo(self, theme: str) -> None:
        self.theme_combo.blockSignals(True)
        index = self.theme_combo.findData(theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
        self.theme_combo.blockSignals(False)

    # -- actions -----------------------------------------------------------
    def _on_quick_theme(self, index: int) -> None:
        theme = self.theme_combo.itemData(index)
        if theme:
            self.app_state.set_theme(theme)

    def _save_quick(self, key: str, value: object) -> None:
        self.config.set(key, value)
        self.config.save()
        self.app_state.set_status(f"{key.replace('_', ' ').title()} set to {value}")
        log.info("Quick setting changed: %s = %s", key, value)

    def _browse_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select video files", "", SUPPORTED_VIDEO_FILTER
        )
        if files:
            self._on_files_dropped(files)

    def _on_files_dropped(self, paths: list[str]) -> None:
        for path in paths:
            job = Job.from_path(path)
            self.app_state.add_job(job)
            self.app_state.add_recent_file(path)
        self.drop_zone.set_file_name(Path(paths[0]).name)
        self.app_state.set_status(f"Queued {len(paths)} file(s) — captioning arrives in a later phase")
        log.info("Accepted %d file(s) into the queue: %s", len(paths), paths)
