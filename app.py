"""AutoCaption Studio — application entry point (Phase 1).

Run with::

    python app.py

The shell builds the whole UI (logging, settings, theme, main window) and
starts the Qt event loop. No AI, transcription or video processing happens
in this phase.
"""

from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.core.app_state import AppState
from src.core.config_manager import ConfigManager
from src.core.constants import APP_NAME, APP_VERSION, LOGO_PATH, ORG_NAME
from src.core.logger import get_logger, install_global_exception_handler, setup_logging
from src.main_window import MainWindow
from src.services.theme_service import ThemeService
from src.services.video_service import VideoService
from src.video import FFmpegManager, FileManager


def main() -> int:
    """Bootstrap and run the application."""
    # --- logging (always first: everything below is logged) ---------------
    logger = setup_logging()
    logger.info("=" * 64)
    logger.info("Application Started (%s v%s)", APP_NAME, APP_VERSION)

    # --- Qt application ---------------------------------------------------
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(APP_VERSION)
    if LOGO_PATH.exists():
        app.setWindowIcon(QIcon(str(LOGO_PATH)))

    # --- global crash handler (dialog instead of silent crash) ------------
    install_global_exception_handler(logger)

    # --- services & state -------------------------------------------------
    config = ConfigManager()
    logger.info("Settings Loaded (%s)", config.path)

    theme_service = ThemeService()
    app_state = AppState(config)

    # Phase 2: media pipeline (validation, metadata, thumbnails, audio).
    ffmpeg = FFmpegManager()
    file_manager = FileManager()
    video_service = VideoService(app_state, ffmpeg, file_manager)
    if video_service.can_process():
        logger.info("FFmpeg available: %s", video_service.ffmpeg_version())
    else:
        logger.warning("FFmpeg not available — video pipeline disabled")

    # --- window -------------------------------------------------------------
    window = MainWindow(config, app_state, theme_service, video_service)
    logger.info("Theme Loaded (%s)", app_state.theme())
    window.show()
    if window.is_startup_maximized():
        window.showMaximized()

    logger.info("Main window shown — ready")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
