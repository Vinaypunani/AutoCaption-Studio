"""Logging setup and global exception handling.

Every application start appends to ``logs/application.log`` (rotating file)
and mirrors warnings/errors to the console. A global exception hook turns
unhandled exceptions into a friendly dialog instead of a silent crash.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

from .constants import LOG_FILE_PATH

_ROOT_LOGGER_NAME = "autocaption"
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_installed = False


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced child logger, e.g. ``autocaption.config``."""
    return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")


def setup_logging(
    log_path: Path = LOG_FILE_PATH,
    level: int = logging.INFO,
    console_level: int = logging.WARNING,
) -> logging.Logger:
    """Configure file + console handlers on the root app logger."""
    root = logging.getLogger(_ROOT_LOGGER_NAME)
    root.setLevel(level)
    root.propagate = False

    # Reset handlers so repeated calls (e.g. in tests) don't stack.
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(_LOG_FORMAT, _DATE_FORMAT)

    file_handler = RotatingFileHandler(
        log_path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setLevel(console_level)
    console.setFormatter(formatter)
    root.addHandler(console)

    root.info("Logging initialised -> %s", log_path)
    return root


def install_global_exception_handler(
    logger: logging.Logger | None = None,
    message_box: Callable[[str, str], None] | None = None,
) -> None:
    """Replace ``sys.excepthook`` so crashes are logged and shown politely.

    ``message_box`` is injected for testability; by default it shows a
    ``QMessageBox`` (only when a QApplication exists, so headless code and
    tests never block on a dialog).
    """
    global _installed
    if _installed:
        return

    log = logger or logging.getLogger(_ROOT_LOGGER_NAME)

    def _default_message_box(title: str, text: str) -> None:
        from PySide6.QtWidgets import QApplication, QMessageBox  # deferred import

        if QApplication.instance() is not None:
            QMessageBox.critical(None, title, text)

    def hook(exc_type, exc_value, exc_tb) -> None:
        # KeyboardInterrupt / SystemExit should propagate normally.
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        log.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
        box = message_box or _default_message_box
        try:
            box("Unexpected Error", "An unexpected error occurred.\nSee logs/application.log for details.")
        except Exception:  # pragma: no cover - never let the hook itself crash
            pass
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = hook
    _installed = True
