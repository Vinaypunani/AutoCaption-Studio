"""Shared test fixtures.

The Qt platform is forced to ``offscreen`` before PySide6 is imported so
the whole suite runs without a display server (also works in CI).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication (offscreen)."""
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def config(tmp_path):
    """ConfigManager writing to a temp directory (isolated per test)."""
    from src.core.config_manager import ConfigManager

    return ConfigManager(path=tmp_path / "settings.json")


@pytest.fixture
def app_state(config):
    from src.core.app_state import AppState

    return AppState(config)


@pytest.fixture
def theme_service():
    from src.services.theme_service import ThemeService

    return ThemeService()


@pytest.fixture
def main_window(qapp, config, app_state, theme_service):
    """A fully-built main window, closed after the test."""
    from src.main_window import MainWindow

    window = MainWindow(config, app_state, theme_service)
    yield window
    window.close()
