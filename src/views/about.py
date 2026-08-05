"""About page — application information (static)."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, qVersion
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core.constants import (
    APP_NAME,
    APP_VERSION,
    AUTHOR,
    GITHUB_URL,
    LICENSE,
    LOGO_PATH,
)
from ..core.logger import get_logger

try:
    from PySide6 import __version__ as PYSIDE_VERSION
except ImportError:  # pragma: no cover
    PYSIDE_VERSION = "unknown"

log = get_logger("about")


class AboutView(QWidget):
    """Application information page."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AboutView")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        outer = QVBoxLayout(body)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        title = QLabel("About")
        title.setObjectName("PageTitle")
        outer.addWidget(title)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(12)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if LOGO_PATH.exists():
            logo_label.setPixmap(QPixmap(str(LOGO_PATH)).scaled(
                96, 96, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        else:
            logo_label.setText("🎬")
            logo_label.setObjectName("DropZoneIcon")
        card_layout.addWidget(logo_label)

        name = QLabel(APP_NAME)
        name.setObjectName("PageTitle")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(name)

        version_chip = QLabel(f"v{APP_VERSION} · Phase 1 — Desktop Application Foundation")
        version_chip.setObjectName("VersionChip")
        version_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(version_chip)

        divider = QFrame()
        divider.setObjectName("Divider")
        divider.setFixedHeight(1)
        card_layout.addWidget(divider)

        info = QGridLayout()
        info.setHorizontalSpacing(24)
        info.setVerticalSpacing(8)

        github_button = QToolButton()
        github_button.setObjectName("LinkButton")
        github_button.setText(GITHUB_URL)
        github_button.setCursor(Qt.CursorShape.PointingHandCursor)
        github_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        github_button.setToolTip("Repository link (placeholder)")
        github_button.clicked.connect(self._on_github_clicked)

        rows = [
            ("Author", AUTHOR),
            ("License", LICENSE),
            ("GitHub", None),
            ("Python", sys.version.split()[0]),
            ("PySide6", PYSIDE_VERSION),
            ("Qt", qVersion()),
        ]
        for row, (key, value) in enumerate(rows):
            key_label = QLabel(key)
            key_label.setObjectName("AboutKey")
            info.addWidget(key_label, row, 0, Qt.AlignmentFlag.AlignLeft)
            if key == "GitHub":
                info.addWidget(github_button, row, 1, Qt.AlignmentFlag.AlignRight)
            else:
                value_label = QLabel(str(value))
                value_label.setObjectName("AboutValue")
                info.addWidget(value_label, row, 1, Qt.AlignmentFlag.AlignRight)
        info.setColumnStretch(0, 1)
        info.setColumnStretch(1, 1)
        card_layout.addLayout(info)

        outer.addWidget(card)
        outer.addStretch(1)

        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    def _on_github_clicked(self) -> None:
        log.info("GitHub link is a placeholder: %s", GITHUB_URL)
