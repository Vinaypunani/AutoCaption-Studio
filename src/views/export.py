"""Export page.

Phase 4: **Subtitle export** is functional — pick a transcribed job, a
format (SRT/ASS/VTT/JSON/TXT) and a folder, and the file is written. Video
export (burned-in captions) remains a Phase 5 placeholder with the same
controls previewed since Phase 1.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core.app_state import AppState
from ..core.config_manager import ConfigManager
from ..core.logger import get_logger
from ..subtitles.subtitle_service import SubtitleService
from ..widgets.cards import make_card, make_field

log = get_logger("export_view")

_ASPECT_RATIOS = ["16:9", "9:16", "1:1", "4:3", "21:9"]
_RESOLUTIONS = ["2160p (4K)", "1440p (QHD)", "1080p (Full HD)", "720p (HD)", "480p (SD)"]
_CODECS = ["H.264", "H.265 / HEVC", "VP9", "AV1"]


class ExportView(QWidget):
    """Export page: subtitle export (Phase 4) + video export placeholder."""

    def __init__(
        self,
        config: ConfigManager,
        app_state: AppState,
        subtitle_service: SubtitleService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.app_state = app_state
        self.subtitle_service = subtitle_service
        self.setObjectName("ExportView")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        outer = QVBoxLayout(body)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        title = QLabel("Export")
        title.setObjectName("PageTitle")
        outer.addWidget(title)

        subtitle = QLabel(
            "Export subtitles for any transcribed job. Video export (burned-in "
            "captions) arrives in the rendering phase."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        # -- subtitle export (Phase 4 — functional) ---------------------------
        sub_widget = QWidget()
        sub_form = QVBoxLayout(sub_widget)
        sub_form.setContentsMargins(0, 0, 0, 0)
        sub_form.setSpacing(10)

        self.job_combo = QComboBox()
        self.job_combo.setObjectName("SettingsCombo")
        self.job_combo.setToolTip("Jobs that have a finished transcription")
        sub_form.addWidget(make_field("Transcribed Job", self.job_combo))

        self.format_combo = QComboBox()
        self.format_combo.setObjectName("SettingsCombo")
        if self.subtitle_service is not None:
            for fmt in self.subtitle_service.available_formats():
                self.format_combo.addItem(fmt.upper(), fmt)
        else:
            self.format_combo.addItems(["SRT", "ASS", "VTT", "JSON", "TXT"])
        sub_form.addWidget(make_field("Subtitle Format", self.format_combo))

        folder_widget = QWidget()
        folder_row = QHBoxLayout(folder_widget)
        folder_row.setContentsMargins(0, 0, 0, 0)
        folder_row.setSpacing(8)
        self.sub_folder_edit = QLineEdit()
        self.sub_folder_edit.setObjectName("SettingsEdit")
        default = str(Path(self.config.get("output_folder", "output")) / "subtitles")
        self.sub_folder_edit.setText(default)
        browse = QPushButton("Browse…")
        browse.setObjectName("GhostButton")
        browse.setCursor(Qt.CursorShape.PointingHandCursor)
        browse.clicked.connect(self._browse_sub_folder)
        folder_row.addWidget(self.sub_folder_edit, 1)
        folder_row.addWidget(browse)
        sub_form.addWidget(make_field("Export To", folder_widget))

        actions = QHBoxLayout()
        actions.setSpacing(8)
        export_button = QPushButton("Export Subtitles")
        export_button.setObjectName("PrimaryButton")
        export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        export_button.clicked.connect(self._export_subtitles)
        actions.addWidget(export_button)
        open_button = QPushButton("Open Folder")
        open_button.setObjectName("GhostButton")
        open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        open_button.clicked.connect(self._open_sub_folder)
        actions.addWidget(open_button)
        actions.addStretch(1)
        sub_form.addLayout(actions)
        outer.addWidget(make_card("Subtitles (Phase 4)", sub_widget))

        # -- video export (Phase 5 — placeholder) -----------------------------
        video_widget = QWidget()
        v_form = QVBoxLayout(video_widget)
        v_form.setContentsMargins(0, 0, 0, 0)
        v_form.setSpacing(10)

        self.aspect_combo = QComboBox()
        self.aspect_combo.setObjectName("SettingsCombo")
        self.aspect_combo.addItems(_ASPECT_RATIOS)
        v_form.addWidget(make_field("Aspect Ratio", self.aspect_combo))

        self.resolution_combo = QComboBox()
        self.resolution_combo.setObjectName("SettingsCombo")
        self.resolution_combo.addItems(_RESOLUTIONS)
        v_form.addWidget(make_field("Resolution", self.resolution_combo))

        self.codec_combo = QComboBox()
        self.codec_combo.setObjectName("SettingsCombo")
        self.codec_combo.addItems(_CODECS)
        v_form.addWidget(make_field("Codec", self.codec_combo))

        self.video_output_edit = QLineEdit()
        self.video_output_edit.setObjectName("SettingsEdit")
        self.video_output_edit.setText(str(self.config.get("output_folder", "output")))
        self.video_output_edit.setToolTip("Video output destination (rendering phase)")
        v_form.addWidget(make_field("Output Folder", self.video_output_edit))

        banner = QLabel("ℹ️  Video export (burned-in captions) ships in the rendering phase. Subtitle files above are ready now.")
        banner.setObjectName("InfoBanner")
        banner.setWordWrap(True)
        v_form.addWidget(banner)
        outer.addWidget(make_card("Video (Phase 5)", video_widget))

        outer.addStretch(1)

        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        self.app_state.jobs_changed.connect(self._refresh_jobs)
        self._refresh_jobs()

    # -- job list ---------------------------------------------------------------
    def _transcribed_jobs(self):
        return [job for job in self.app_state.jobs() if job.transcript]

    def _refresh_jobs(self) -> None:
        self.job_combo.clear()
        jobs = self._transcribed_jobs()
        for job in jobs:
            self.job_combo.addItem(job.filename, job.job_id)
        self.job_combo.setEnabled(bool(jobs))
        self.job_combo.setPlaceholderText("No transcribed jobs yet" if not jobs else "")

    # -- actions ------------------------------------------------------------------
    def _export_subtitles(self) -> None:
        if self.subtitle_service is None:
            self.app_state.set_status("Subtitle engine unavailable")
            return
        job_id = self.job_combo.currentData()
        job = next((j for j in self.app_state.jobs() if j.job_id == job_id), None)
        if job is None:
            self.app_state.set_status("Select a transcribed job to export")
            return
        fmt = self.format_combo.currentData() or "srt"
        folder = self.sub_folder_edit.text().strip()
        if not folder:
            self.app_state.set_status("Choose an export folder")
            return
        try:
            target = self.subtitle_service.export(job, fmt, folder)
            self.app_state.set_status(f"Exported {job.filename} → {target}")
            log.info("Exported subtitles for %s to %s", job.filename, target)
        except Exception as exc:  # pragma: no cover - defensive
            self.app_state.set_status(f"Export failed: {exc}")
            log.exception("Subtitle export failed")

    def _browse_sub_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose export folder")
        if folder:
            self.sub_folder_edit.setText(folder)

    def _open_sub_folder(self) -> None:
        folder = self.sub_folder_edit.text().strip()
        if folder and Path(folder).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
