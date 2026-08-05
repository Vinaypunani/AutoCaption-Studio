"""Sidebar navigation widget.

Emits :data:`Sidebar.navigate_requested` with a page id whenever a nav
button is clicked. The main window decides which page to show.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core.constants import APP_VERSION

# page_id -> button label
PAGE_ITEMS: list[tuple[str, str]] = [
    ("home", "🏠  Home"),
    ("queue", "📁  Queue"),
    ("settings", "⚙️  Settings"),
    ("export", "📤  Export"),
    ("about", "ℹ️  About"),
]
PAGE_ORDER = [page_id for page_id, _ in PAGE_ITEMS]
PAGE_LABELS = dict(PAGE_ITEMS)


class SidebarButton(QToolButton):
    """A single, checkable navigation entry."""

    def __init__(self, text: str, page_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.page_id = page_id
        self.setObjectName("SidebarButton")
        self.setText(text)
        self.setCheckable(True)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


class Sidebar(QWidget):
    """Left navigation rail containing the app brand and nav buttons."""

    navigate_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(216)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 12)
        layout.setSpacing(6)

        brand = QLabel("🎬 AutoCaption")
        brand.setObjectName("SidebarTitle")
        layout.addWidget(brand)

        subtitle = QLabel("Studio · Phase 1")
        subtitle.setObjectName("SidebarSubtitle")
        layout.addWidget(subtitle)
        layout.addSpacing(14)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, SidebarButton] = {}

        for page_id, label in PAGE_ITEMS:
            button = SidebarButton(label, page_id)
            button.clicked.connect(lambda _checked=False, pid=page_id: self.navigate_requested.emit(pid))
            self._group.addButton(button)
            layout.addWidget(button)
            self._buttons[page_id] = button

        layout.addStretch(1)

        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("SidebarVersion")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        self.set_active("home")

    # -- API ---------------------------------------------------------------
    def set_active(self, page_id: str) -> None:
        """Visually select the button for ``page_id``."""
        button = self._buttons.get(page_id)
        if button is not None:
            button.setChecked(True)

    def buttons(self) -> list[SidebarButton]:
        return list(self._buttons.values())
