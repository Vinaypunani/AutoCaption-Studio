"""Main application window — composition root for the whole UI.

Arranges TopBar / Sidebar / page stack / StatusBar, owns navigation and
theme application, and handles the frameless window's drag & resize
behaviour (via an application-level event filter).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizeGrip,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .core.app_state import AppState
from .core.config_manager import ConfigManager
from .core.constants import APP_NAME, LOGO_PATH, MIN_WINDOW_HEIGHT, MIN_WINDOW_WIDTH
from .core.logger import get_logger
from .services.theme_service import ThemeService
from .views.about import AboutView
from .views.export import ExportView
from .views.home import HomeView
from .views.queue import QueueView
from .views.settings import SettingsView
from .widgets.progress_widget import ProgressWidget
from .widgets.sidebar import PAGE_LABELS, PAGE_ORDER, Sidebar
from .widgets.topbar import TopBar

log = get_logger("main_window")

RESIZE_MARGIN = 6
_EDGE_MODES = ("left", "right", "top", "bottom", "tl", "tr", "bl", "br")


class MainWindow(QMainWindow):
    """Frameless application shell with sidebar navigation."""

    def __init__(
        self,
        config: ConfigManager,
        app_state: AppState,
        theme_service: ThemeService,
        video_service=None,  # services.video_service.VideoService (optional)
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.app_state = app_state
        self.theme_service = theme_service
        self.video_service = video_service

        self._drag_mode: Optional[str] = None
        self._drag_start_global = QPoint()
        self._drag_start_geom = self.geometry()

        self.setObjectName("MainWindow")
        self.setWindowTitle(f"{APP_NAME} — Phase 1")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))

        self._build_ui()
        self._connect_signals()

        self._restore_geometry()
        self.apply_theme(self.app_state.theme())

        # Application-level event filter so mouse events over any child
        # widget still drive frameless drag & edge-resize.
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("MainWindow")
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.topbar = TopBar(self.app_state)
        root.addWidget(self.topbar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.sidebar = Sidebar()
        body_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.pages: dict[str, QWidget] = {
            "home": HomeView(self.app_state, self.theme_service, self.config, self.video_service),
            "queue": QueueView(self.app_state, self.video_service),
            "settings": SettingsView(self.app_state, self.theme_service, self.config),
            "export": ExportView(self.config),
            "about": AboutView(),
        }
        for page_id in PAGE_ORDER:
            self.stack.addWidget(self.pages[page_id])
        body_layout.addWidget(self.stack, 1)
        root.addWidget(body, 1)

        status_bar = QFrame()
        status_bar.setObjectName("StatusBar")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(12, 3, 6, 3)
        status_layout.setSpacing(8)
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("StatusBarLabel")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch(1)
        grip = QSizeGrip(status_bar)
        grip.setFixedSize(16, 16)
        status_layout.addWidget(grip)
        root.addWidget(status_bar)

        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self.sidebar.navigate_requested.connect(self.navigate)
        self.app_state.status_message.connect(self.set_status)
        self.app_state.theme_changed.connect(self.apply_theme)
        self.pages["home"].navigate_requested.connect(self.navigate)

    # ------------------------------------------------------------ navigation
    def navigate(self, page_id: str) -> None:
        """Switch the visible page and sync the sidebar highlight."""
        if page_id not in self.pages:
            log.warning("Unknown page requested: %s", page_id)
            return
        self.stack.setCurrentWidget(self.pages[page_id])
        self.sidebar.set_active(page_id)
        label = PAGE_LABELS.get(page_id, page_id)
        self.set_status(f"Page: {label}")
        log.info("Navigation -> %s", page_id)

    def current_page_id(self) -> Optional[str]:
        widget = self.stack.currentWidget()
        for page_id, view in self.pages.items():
            if view is widget:
                return page_id
        return None

    # ----------------------------------------------------------------- theme
    def apply_theme(self, theme: str) -> None:
        """Apply a stylesheet app-wide and refresh custom-painted widgets."""
        self.theme_service.apply(theme)
        for progress in self.findChildren(ProgressWidget):
            progress.update()

    # ---------------------------------------------------------------- status
    def set_status(self, message: str) -> None:
        self.status_label.setText(message)

    # ------------------------------------------------------------ window mgmt
    def start_window_drag(self, global_pos: QPoint) -> None:
        """Begin moving the window (called by the top bar)."""
        if self.isMaximized():
            return
        self._drag_mode = "move"
        self._drag_start_global = global_pos
        self._drag_start_geom = self.geometry()

    def _edge_mode_at(self, local_pos: QPoint) -> Optional[str]:
        rect = self.rect()
        if not rect.contains(local_pos):
            return None
        left = local_pos.x() <= RESIZE_MARGIN
        right = local_pos.x() >= rect.width() - RESIZE_MARGIN
        top = local_pos.y() <= RESIZE_MARGIN
        bottom = local_pos.y() >= rect.height() - RESIZE_MARGIN
        if top and left:
            return "tl"
        if top and right:
            return "tr"
        if bottom and left:
            return "bl"
        if bottom and right:
            return "br"
        if left:
            return "left"
        if right:
            return "right"
        if top:
            return "top"
        if bottom:
            return "bottom"
        return None

    _EDGE_CURSORS = {
        "left": Qt.CursorShape.SizeHorCursor,
        "right": Qt.CursorShape.SizeHorCursor,
        "top": Qt.CursorShape.SizeVerCursor,
        "bottom": Qt.CursorShape.SizeVerCursor,
        "tl": Qt.CursorShape.SizeFDiagCursor,
        "br": Qt.CursorShape.SizeFDiagCursor,
        "tr": Qt.CursorShape.SizeBDiagCursor,
        "bl": Qt.CursorShape.SizeBDiagCursor,
    }

    def _resize_from_edge(self, global_pos: QPoint) -> None:
        start = QRect(self._drag_start_geom)
        delta = global_pos - self._drag_start_global
        mode = self._drag_mode or ""
        if mode in ("left", "tl", "bl"):
            start.setLeft(min(start.left() + delta.x(), start.right() - self.minimumWidth()))
        if mode in ("right", "tr", "br"):
            start.setRight(max(start.right() + delta.x(), start.left() + self.minimumWidth()))
        if mode in ("top", "tl", "tr"):
            start.setTop(min(start.top() + delta.y(), start.bottom() - self.minimumHeight()))
        if mode in ("bottom", "bl", "br"):
            start.setBottom(max(start.bottom() + delta.y(), start.top() + self.minimumHeight()))
        self.setGeometry(start)

    # -------------------------------------------------- frameless event filter
    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt naming)
        if (
            isinstance(obj, QWidget)
            and obj.window() is self
            and not self.isMaximized()
        ):
            event_type = event.type()
            if event_type == QEvent.Type.MouseMove:
                global_pos = event.globalPosition().toPoint()
                if self._drag_mode == "move":
                    self.move(self._drag_start_geom.topLeft() + global_pos - self._drag_start_global)
                    return True
                if self._drag_mode in _EDGE_MODES:
                    self._resize_from_edge(global_pos)
                    return True
                mode = self._edge_mode_at(obj.mapTo(self, event.position().toPoint()))
                cursor = self._EDGE_CURSORS.get(mode) if mode else Qt.CursorShape.ArrowCursor
                if self.cursor().shape() != cursor:
                    self.setCursor(QCursor(cursor))
            elif event_type == QEvent.Type.Leave and obj is self and not self._drag_mode:
                # The mouse left the window; drop any edge-resize cursor.
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            elif event_type == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                mode = self._edge_mode_at(obj.mapTo(self, event.position().toPoint()))
                if mode:
                    self._drag_mode = mode
                    self._drag_start_global = event.globalPosition().toPoint()
                    self._drag_start_geom = self.geometry()
            elif event_type == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                if self._drag_mode:
                    self._drag_mode = None
                    self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
                    return True
        return super().eventFilter(obj, event)

    # --------------------------------------------------------------- geometry
    def _restore_geometry(self) -> None:
        window = self.config.get("window", {})
        if not isinstance(window, dict):
            return
        width = int(window.get("width", MIN_WINDOW_WIDTH))
        height = int(window.get("height", MIN_WINDOW_HEIGHT))
        x = window.get("x")
        y = window.get("y")
        if isinstance(x, int) and isinstance(y, int):
            self.setGeometry(x, y, width, height)
        else:
            self.resize(width, height)

    def is_startup_maximized(self) -> bool:
        return bool(self.config.get("window", {}).get("maximized", False))

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.config.set("window", {
            "width": self.width(),
            "height": self.height(),
            "x": self.x(),
            "y": self.y(),
            "maximized": self.isMaximized(),
        })
        self.config.save()
        if self.video_service is not None:
            self.video_service.shutdown()
        log.info("Application closing; window geometry saved")
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        super().closeEvent(event)
