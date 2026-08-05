"""Central application constants and path helpers.

Everything location-related is derived from this module so later phases can
reuse the same conventions (and so tests/CI can redirect directories via
environment variables).
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
APP_NAME = "AutoCaption Studio"
APP_SLUG = "autocaption-studio"
APP_VERSION = "0.1.0"  # Phase 1
ORG_NAME = "AutoCaptionStudio"
AUTHOR = "AutoCaption Studio Team"
LICENSE = "MIT"
GITHUB_URL = "https://github.com/yourusername/autocaption-studio"  # placeholder

# ---------------------------------------------------------------------------
# Paths (all relative to the project root, unless overridden by env vars)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]

ASSETS_DIR = PROJECT_ROOT / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
FONTS_DIR = ASSETS_DIR / "fonts"
IMAGES_DIR = ASSETS_DIR / "images"
LOGO_PATH = ASSETS_DIR / "logo.png"

CONFIG_DIR = Path(os.environ.get("AUTOCAPTION_CONFIG_DIR", PROJECT_ROOT / "config"))
SETTINGS_PATH = CONFIG_DIR / "settings.json"
THEMES_CATALOG_PATH = CONFIG_DIR / "themes.json"

THEMES_DIR = Path(os.environ.get("AUTOCAPTION_THEMES_DIR", PROJECT_ROOT / "themes"))

LOGS_DIR = Path(os.environ.get("AUTOCAPTION_LOGS_DIR", PROJECT_ROOT / "logs"))
LOG_FILE_PATH = LOGS_DIR / "application.log"

OUTPUT_DIR = PROJECT_ROOT / "output"
TEMP_DIR = PROJECT_ROOT / "temp"

# ---------------------------------------------------------------------------
# Video file support (Phase 1: detection only — no processing)
# ---------------------------------------------------------------------------
SUPPORTED_VIDEO_EXTS = {
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv",
    ".m4v", ".mpg", ".mpeg", ".3gp", ".ts", ".ogv",
}

SUPPORTED_VIDEO_FILTER = "Video files (" + " ".join(f"*{ext}" for ext in sorted(SUPPORTED_VIDEO_EXTS)) + ")"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_SETTINGS: dict = {
    "theme": "dark",
    "language": "English",
    "gpu": True,
    "output_folder": "output",
    "autosave": True,
    "update_channel": "stable",
    "recent_files": [],
    "window": {"width": 1280, "height": 800, "maximized": False},
}

MAX_RECENT_FILES = 5
MIN_WINDOW_WIDTH = 960
MIN_WINDOW_HEIGHT = 620
