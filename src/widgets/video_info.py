"""Video Information panel — displays thumbnail + metadata grid.

Reused on the Home page (latest processed video) and the Queue page
(selected job). Pass a :class:`VideoMetadata` (or ``None`` to clear).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..core.constants import THUMBNAIL_EXT
from ..video.metadata import VideoMetadata, format_bitrate, format_bytes, format_duration

# (label, getter) — order matches the metadata spec.
_FIELDS: list[tuple[str, str]] = [
    ("Filename", "filename"),
    ("Extension", "extension"),
    ("Duration", "duration_display"),
    ("Resolution", "resolution"),
    ("Aspect Ratio", "aspect_ratio"),
    ("FPS", "fps"),
    ("Video Codec", "video_codec"),
    ("Bitrate", "bitrate_display"),
    ("Audio Codec", "audio_codec"),
    ("Audio Channels", "channels_display"),
    ("File Size", "size_display"),
    ("Created", "creation_date"),
]


class VideoInfoPanel(QFrame):
    """Thumbnail + full metadata grid for one video."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(12)

        header = QLabel("Video Information")
        header.setObjectName("CardTitle")
        layout.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(16)

        # -- thumbnail ------------------------------------------------------
        thumb_column = QVBoxLayout()
        thumb_column.setSpacing(6)
        self.thumb_label = QLabel()
        self.thumb_label.setObjectName("ThumbLabel")
        self.thumb_label.setFixedSize(200, 112)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_placeholder("🎬")
        thumb_column.addWidget(self.thumb_label)
        thumb_column.addStretch(1)
        body.addLayout(thumb_column)

        # -- metadata grid ---------------------------------------------------
        self._values: dict[str, QLabel] = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(5)
        grid.setColumnStretch(1, 1)
        for row, (label_text, key) in enumerate(_FIELDS):
            label = QLabel(label_text)
            label.setObjectName("AboutKey")
            value = QLabel("—")
            value.setObjectName("AboutValue")
            value.setWordWrap(False)
            grid.addWidget(label, row, 0, Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(value, row, 1, Qt.AlignmentFlag.AlignLeft)
            self._values[key] = value
        body.addLayout(grid, 1)

        layout.addLayout(body)
        self.clear()

    # -- API -----------------------------------------------------------------
    def set_metadata(self, metadata: Optional[VideoMetadata], thumbnail_path: Optional[str] = None) -> None:
        """Populate the panel; ``None`` clears it. Thumbnail comes from the job."""
        if metadata is None:
            self.clear()
            return
        for key, label in self._values.items():
            label.setText(self._display(metadata, key))
        self._show_thumbnail(thumbnail_path)

    def _show_thumbnail(self, thumbnail_path: Optional[str]) -> None:
        if thumbnail_path and Path(thumbnail_path).exists():
            pixmap = QPixmap(str(thumbnail_path))
            if not pixmap.isNull():
                self.thumb_label.setPixmap(pixmap.scaled(
                    200, 112,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
                return
        self._set_placeholder("🎬")

    def clear(self) -> None:
        for label in self._values.values():
            label.setText("—")
        self._set_placeholder("🎬")

    # -- helpers ----------------------------------------------------------------
    @staticmethod
    def _display(metadata: VideoMetadata, key: str) -> str:
        value = getattr(metadata, key, None)
        if value is None:
            return "—"
        if key == "fps":
            return f"{value:.1f}" if isinstance(value, float) and value else "—"
        if key == "extension":
            return value.lstrip(".") if isinstance(value, str) else str(value)
        return str(value)

    def _set_placeholder(self, glyph: str) -> None:
        self.thumb_label.setPixmap(QPixmap())
        self.thumb_label.setText(glyph)
