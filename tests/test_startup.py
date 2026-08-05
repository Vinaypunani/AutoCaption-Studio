"""Startup behaviour: logging, exception hook, window construction, themes."""

import sys

from src.core.constants import APP_NAME, LOG_FILE_PATH
from src.core.logger import install_global_exception_handler, setup_logging


def test_log_file_created_on_boot():
    root = setup_logging()
    root.info("boot marker message")
    assert LOG_FILE_PATH.exists()
    assert "boot marker message" in LOG_FILE_PATH.read_text(encoding="utf-8", errors="replace")


def test_exception_hook_installed():
    # Pass a no-op message box: the real hook would raise a modal dialog for
    # the rest of the test session, which could hang the suite.
    install_global_exception_handler(message_box=lambda title, text: None)
    assert sys.excepthook is not sys.__excepthook__


def test_window_builds_and_has_five_pages(qapp, config, app_state, theme_service):
    from src.main_window import MainWindow

    window = MainWindow(config, app_state, theme_service)
    assert APP_NAME in window.windowTitle()
    assert window.stack.count() == 5
    window.close()


def test_theme_stylesheets_are_non_empty(theme_service):
    for theme in theme_service.available_themes():
        assert theme_service.stylesheet(theme).strip(), f"theme {theme} has no QSS"


def test_app_state_seeds_and_clears_jobs(app_state):
    app_state.seed_mock_jobs()
    assert len(app_state.jobs()) == 4
    app_state.clear_jobs()
    assert app_state.jobs() == []
