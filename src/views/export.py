"""Export page.

Placeholder controls only — no export logic in Phase 1. The controls
preview what the export flow will offer in later phases.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core.config_manager import ConfigManager
from ..widgets.cards import make_card

_ASPECT_RATIOS = ["16:9", "9:16", "1:1", "4:3", "21:9"]
_RESOLUTIONS = ["2160p (4K)", "1440p (QHD)", "1080p (Full HD)", "720p (HD)", "480p (SD)"]
_CODECS = ["H.264", "H.265 / HEVC", "VP9", "AV1"]


class ExportView(QWidget):
    """Export placeholder page."""

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
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
            "Export controls — placeholder only. The export engine ships in a later phase."
        )
        subtitle.setObjectName("PageSubtitle")
        outer.addWidget(subtitle)

        banner = QLabel("ℹ️  Export is not implemented in Phase 1. These controls preview the future export flow.")
        banner.setObjectName("InfoBanner")
        banner.setWordWrap(True)
        outer.addWidget(banner)

        # -- format card ----------------------------------------------------
        format_widget = QWidget()
        form = QVBoxLayout(format_widget)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        self.aspect_combo = QComboBox()
        self.aspect_combo.setObjectName("SettingsCombo")
        self.aspect_combo.addItems(_ASPECT_RATIOS)
        form.addWidget(self._field("Aspect Ratio", self.aspect_combo))

        self.resolution_combo = QComboBox()
        self.resolution_combo.setObjectName("SettingsCombo")
        self.resolution_combo.addItems(_RESOLUTIONS)
        form.addWidget(self._field("Resolution", self.resolution_combo))

        self.codec_combo = QComboBox()
        self.codec_combo.setObjectName("SettingsCombo")
        self.codec_combo.addItems(_CODECS)
        form.addWidget(self._field("Codec", self.codec_combo))
        outer.addWidget(make_card("Format", format_widget))

        # -- destination card -------------------------------------------------
        dest_widget = QWidget()
        dest_form = QVBoxLayout(dest_widget)
        dest_form.setContentsMargins(0, 0, 0, 0)
        dest_form.setSpacing(10)

        self.output_edit = QLineEdit()
        self.output_edit.setObjectName("SettingsEdit")
        self.output_edit.setText(str(self.config.get("output_folder", "output")))
        self.output_edit.setToolTip("Output destination (used by later phases)")
        dest_form.addWidget(self._field("Output Folder", self.output_edit))
        outer.addWidget(make_card("Destination", dest_widget))

        # -- actions -----------------------------------------------------------
        export_button = QPushButton("Export")
        export_button.setObjectName("PrimaryButton")
        export_button.setEnabled(False)
        export_button.setToolTip("Available in a later phase")
        export_button.setCursor(Qt.CursorShape.ForbiddenCursor)
        outer.addWidget(export_button, 0, Qt.AlignmentFlag.AlignLeft)

        outer.addStretch(1)

        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    @staticmethod
    def _field(label_text: str, widget: QWidget) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(label_text)
        label.setObjectName("FieldLabel")
        layout.addWidget(label)
        layout.addWidget(widget)
        return row
