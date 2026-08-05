"""Home page.

Phase 2 behaviour: dropped videos are validated immediately (unsupported
formats get a clear message) and queued; the pipeline service then extracts
metadata, generates a thumbnail and extracts audio. The Video Information
panel shows the latest processed video's details.
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
    QScrollArea,
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
from ..video.validator import is_supported_extension
from ..widgets.cards import make_card, make_field
from ..widgets.drop_zone import DropZone
from ..widgets.queue_widget import QueueWidget
from ..widgets.video_info import VideoInfoPanel

log = get_logger("home")


class HomeView(QWidget):
    """Dashboard page."""

    navigate_requested = Signal(str)  # e.g. "queue"

    def __init__(
        self,
        app_state: AppState,
        theme_service: ThemeService,
        config: ConfigManager,
        video_service=None,  # services.video_service.VideoService (optional)
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_state = app_state
        self.theme_service = theme_service
        self.config = config
        self.video_service = video_service
        self.setObjectName("HomeView")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        body = QWidget()
        outer = QVBoxLayout(body)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        title = QLabel("Home")
        title.setObjectName("PageTitle")
        outer.addWidget(title)

        subtitle = QLabel(
            "Drop a video to validate it, extract metadata, generate a thumbnail "
            "and prepare its audio. Caption generation arrives in Phase 3."
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
        side_row.addWidget(self._build_recent_files(), 1)
        side_row.addWidget(self._build_quick_settings(), 1)
        outer.addLayout(side_row)

        # -- video information (latest processed video) ---------------------
        self.video_info = VideoInfoPanel()
        outer.addWidget(self.video_info)

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

        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

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
        layout.addWidget(make_field("Theme", self.theme_combo))

        self.gpu_check = QCheckBox("Use GPU acceleration")
        self.gpu_check.setChecked(bool(self.config.get("gpu", True)))
        self.gpu_check.setToolTip("Reserved for Phase 3 captioning")
        self.gpu_check.toggled.connect(lambda checked: self._save_quick("gpu", checked))
        layout.addWidget(self.gpu_check)

        self.autosave_check = QCheckBox("Autosave projects")
        self.autosave_check.setChecked(bool(self.config.get("autosave", True)))
        self.autosave_check.toggled.connect(lambda checked: self._save_quick("autosave", checked))
        layout.addWidget(self.autosave_check)

        layout.addStretch(1)
        return container

    # -- state wiring ------------------------------------------------------
    def _connect_state(self) -> None:
        self.app_state.recent_files_changed.connect(lambda _files: self._refresh_recent_files())
        self.app_state.jobs_changed.connect(self._refresh_state)
        self.app_state.theme_changed.connect(self._sync_theme_combo)
        self._refresh_state()

    def _refresh_state(self) -> None:
        self.mini_queue.set_jobs(self.app_state.jobs())
        self._refresh_video_info()

    def _refresh_recent_files(self) -> None:
        self.recent_list.clear()
        for path in self.app_state.recent_files():
            name = Path(path).name or path
            self.recent_list.addItem(f"🎞️  {name}")
            item = self.recent_list.item(self.recent_list.count() - 1)
            item.setToolTip(path)

    def _refresh_video_info(self) -> None:
        """Show the most recent job that has real metadata."""
        for job in reversed(self.app_state.jobs()):
            if job.metadata is not None:
                self.video_info.set_metadata(job.metadata, job.thumbnail_path)
                return
        self.video_info.clear()

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
        accepted: list[str] = []
        for path in paths:
            if is_supported_extension(path):
                accepted.append(path)
            else:
                log.warning("Rejected unsupported format: %s", path)
                self.app_state.set_status(
                    f"Unsupported video format: {Path(path).name}. "
                    f"Supported: mp4, mov, avi, mkv, webm, m4v"
                )

        if not accepted:
            return

        can_process = self.video_service is not None and self.video_service.can_process()
        for index, path in enumerate(accepted):
            job = Job.from_path(path)
            self.app_state.add_job(job)
            self.app_state.add_recent_file(path, persist=index == len(accepted) - 1)
            if can_process:
                self.video_service.process_job(job.job_id)

        self.drop_zone.set_file_name(Path(accepted[0]).name)
        if can_process:
            message = f"Queued {len(accepted)} file(s) for processing"
        else:
            message = f"Queued {len(accepted)} file(s) — FFmpeg not available, processing disabled"
        self.app_state.set_status(message)
        log.info("Accepted %d file(s) into the queue: %s", len(accepted), accepted)
