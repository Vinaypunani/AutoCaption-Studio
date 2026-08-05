"""Drag & drop zone for video files.

Phase 1 behavior is *detection only*: accepted video paths are emitted
through :data:`DropZone.files_dropped`. Nothing is read, probed or processed.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.constants import SUPPORTED_VIDEO_EXTS, SUPPORTED_VIDEO_FILTER
from ..core.logger import get_logger

log = get_logger("drop_zone")


def is_supported_video(path: str | Path) -> bool:
    """True if the file extension is in the supported video set."""
    return Path(path).suffix.lower() in SUPPORTED_VIDEO_EXTS


class DropZone(QFrame):
    """Clickable / draggable video drop target (UI only)."""

    files_dropped = Signal(list)   # list[str] of accepted video paths
    browse_clicked = Signal()      # user asked to open the file dialog

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(230)

        self._drag_active = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(6)

        icon = QLabel("🎬")
        icon.setObjectName("DropZoneIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        title = QLabel("Drag & Drop Video Here")
        title.setObjectName("DropZoneTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        hint = QLabel("MP4 · MKV · MOV · AVI · WebM · more — or click to browse")
        hint.setObjectName("DropZoneHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        self.file_label = QLabel("")
        self.file_label.setObjectName("DroppedFileLabel")
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_label.setWordWrap(True)
        self.file_label.hide()
        layout.addWidget(self.file_label)

        layout.addSpacing(6)

        browse = QPushButton("Browse Files")
        browse.setObjectName("PrimaryButton")
        browse.setCursor(Qt.CursorShape.PointingHandCursor)
        browse.clicked.connect(self.browse_clicked.emit)
        layout.addWidget(browse, 0, Qt.AlignmentFlag.AlignHCenter)

    # -- public API --------------------------------------------------------
    def set_file_name(self, name: str | None) -> None:
        """Show the most recently accepted file name (or hide it)."""
        if name:
            self.file_label.setText(f"📄 {name}")
            self.file_label.show()
        else:
            self.file_label.clear()
            self.file_label.hide()

    # -- drag & drop handling ---------------------------------------------
    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self._has_video(event.mimeData()):
            event.acceptProposedAction()
            self._set_drag_active(True)
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self._has_video(event.mimeData()):
            event.acceptProposedAction()
            self._set_drag_active(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self._set_drag_active(False)
        event.accept()

    def dropEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self._set_drag_active(False)
        urls = event.mimeData().urls()
        accepted = [
            url.toLocalFile()
            for url in urls
            if url.isLocalFile() and is_supported_video(url.toLocalFile())
        ]
        if accepted:
            log.info("Drop accepted: %s", accepted)
            self.files_dropped.emit(accepted)
            self.set_file_name(Path(accepted[0]).name)
            event.acceptProposedAction()
        else:
            event.ignore()

    # -- click to browse ---------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.MouseButton.LeftButton:
            self.browse_clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _has_video(mime_data) -> bool:
        if not mime_data.hasUrls():
            return False
        return any(
            url.isLocalFile() and is_supported_video(url.toLocalFile())
            for url in mime_data.urls()
        )

    def _set_drag_active(self, active: bool) -> None:
        if active == self._drag_active:
            return
        self._drag_active = active
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)
