"""Custom top bar (title bar).

Because the main window is frameless, this widget acts as the title bar:
it drags the window around, toggles the theme and owns the minimize /
maximize / close controls.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QWidget

from ..core.app_state import AppState
from ..core.constants import APP_NAME
from ..core.logger import get_logger

log = get_logger("topbar")


class TopBar(QFrame):
    """Application title bar with window controls."""

    def __init__(self, app_state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app_state = app_state
        self.setObjectName("TopBar")
        self.setFixedHeight(46)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 10, 0)
        layout.setSpacing(8)

        logo = QLabel("🎬")
        logo.setObjectName("TopBarLogo")
        layout.addWidget(logo)

        self.title = QLabel(APP_NAME)
        self.title.setObjectName("TopBarTitle")
        layout.addWidget(self.title)
        layout.addStretch(1)

        self.theme_button = QToolButton()
        self.theme_button.setObjectName("ThemeButton")
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.theme_button.setToolTip("Switch theme")
        self.theme_button.clicked.connect(self._on_theme_clicked)
        layout.addWidget(self.theme_button)

        self.min_button = QToolButton()
        self.min_button.setObjectName("WinButton")
        self.min_button.setText("─")
        self.min_button.setToolTip("Minimize")
        self.min_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.min_button.setFixedSize(42, 32)
        self.min_button.clicked.connect(lambda: self.window().showMinimized())
        layout.addWidget(self.min_button)

        self.max_button = QToolButton()
        self.max_button.setObjectName("WinButton")
        self.max_button.setText("▢")
        self.max_button.setToolTip("Maximize")
        self.max_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.max_button.setFixedSize(42, 32)
        self.max_button.clicked.connect(self._toggle_maximize)
        layout.addWidget(self.max_button)

        self.close_button = QToolButton()
        self.close_button.setObjectName("CloseButton")
        self.close_button.setText("✕")
        self.close_button.setToolTip("Close")
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setFixedSize(42, 32)
        self.close_button.clicked.connect(lambda: self.window().close())
        layout.addWidget(self.close_button)

        self.app_state.theme_changed.connect(self._sync_theme_icon)
        self._sync_theme_icon(self.app_state.theme())

    # -- theme -------------------------------------------------------------
    def _on_theme_clicked(self) -> None:
        new_theme = "light" if self.app_state.theme() == "dark" else "dark"
        log.info("Theme toggle requested: %s -> %s", self.app_state.theme(), new_theme)
        self.app_state.set_theme(new_theme)

    def _sync_theme_icon(self, theme: str) -> None:
        if theme == "dark":
            self.theme_button.setText("☀️")
            self.theme_button.setToolTip("Switch to light theme")
        else:
            self.theme_button.setText("🌙")
            self.theme_button.setToolTip("Switch to dark theme")

    # -- window controls ---------------------------------------------------
    def _toggle_maximize(self) -> None:
        window = self.window()
        if window.isMaximized():
            window.showNormal()
            self.max_button.setText("▢")
        else:
            window.showMaximized()
            self.max_button.setText("❐")

    # -- drag-to-move ------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.MouseButton.LeftButton:
            window = self.window()
            if hasattr(window, "start_window_drag"):
                window.start_window_drag(event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self._toggle_maximize()
        event.accept()
