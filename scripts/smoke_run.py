"""Headless smoke run for AutoCaption Studio.

Boots the complete application offscreen (no display needed), exercises
navigation, the job queue, theme switching and window rendering, then writes
preview images to ``output/preview_*.png`` for visual inspection.

Usage:  python scripts/smoke_run.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Isolate this run's config/logs so the shipped defaults stay pristine.
_SMOKE_ROOT = Path(os.environ.get("SMOKE_ROOT", Path(__file__).resolve().parents[1] / "temp" / "smoke"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["AUTOCAPTION_CONFIG_DIR"] = str(_SMOKE_ROOT / "config")
os.environ["AUTOCAPTION_LOGS_DIR"] = str(_SMOKE_ROOT / "logs")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from src.core.app_state import AppState  # noqa: E402
from src.core.config_manager import ConfigManager  # noqa: E402
from src.core.constants import APP_NAME, LOG_FILE_PATH, OUTPUT_DIR  # noqa: E402
from src.core.logger import get_logger, setup_logging  # noqa: E402
from src.main_window import MainWindow  # noqa: E402
from src.services.theme_service import ThemeService  # noqa: E402

PAGES = ["home", "queue", "settings", "export", "about"]


def main() -> int:
    logger = setup_logging()
    logger.info("Smoke run starting (%s)", APP_NAME)

    app = QApplication(sys.argv)

    # Give the isolated config dir the same theme catalog as the real one
    # (the real catalog lives next to the real config dir, not the override).
    source_catalog = Path(__file__).resolve().parents[1] / "config" / "themes.json"
    if source_catalog.exists():
        _SMOKE_ROOT.joinpath("config").mkdir(parents=True, exist_ok=True)
        (_SMOKE_ROOT / "config" / "themes.json").write_text(
            source_catalog.read_text(encoding="utf-8"), encoding="utf-8"
        )

    config = ConfigManager()
    app_state = AppState(config)
    theme_service = ThemeService()

    window = MainWindow(config, app_state, theme_service)
    window.show()
    window.resize(1280, 800)
    app.processEvents()

    # 1) Navigate through every page (must not raise).
    for page_id in PAGES:
        window.navigate(page_id)
        app.processEvents()
    logger.info("Navigation across all pages OK")

    # 2) Seed sample jobs and let the demo timer advance a tick or two.
    app_state.seed_mock_jobs()
    window.navigate("queue")
    app.processEvents()
    window.grab().save(str(OUTPUT_DIR / "preview_queue_dark.png"))

    # 3) Home preview + light theme + settings page.
    window.navigate("home")
    app.processEvents()
    window.grab().save(str(OUTPUT_DIR / "preview_home_dark.png"))

    app_state.set_theme("light")
    window.navigate("settings")
    app.processEvents()
    window.grab().save(str(OUTPUT_DIR / "preview_settings_light.png"))

    logger.info("Smoke run finished; log file: %s", LOG_FILE_PATH)
    assert LOG_FILE_PATH.exists(), "log file was not created"
    print("smoke run OK — previews written to output/preview_*.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
