"""Theme service — loads QSS and exposes accent colors to custom widgets.

Themes are described in ``config/themes.json`` and the QSS lives in
``themes/<key>.qss``. The service applies stylesheets at the application
level so every widget is themed consistently, and publishes the accent /
track colors used by custom-painted widgets (e.g. the progress bar).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget

from ..core.constants import THEMES_CATALOG_PATH, THEMES_DIR
from ..core.logger import get_logger

log = get_logger("theme")

# ---------------------------------------------------------------------------
# Module-level palette for custom-painted widgets (no instance plumbing).
# Updated by ThemeService whenever a theme is applied.
# ---------------------------------------------------------------------------
_ACCENT = "#6c8cff"
_TRACK = "#2b2e37"


def accent_color() -> str:
    """Current theme accent color (hex) for custom-painted widgets."""
    return _ACCENT


def track_color() -> str:
    """Current theme track color (hex) for custom-painted widgets."""
    return _TRACK


def set_palette(accent: str, track: str) -> None:
    global _ACCENT, _TRACK
    _ACCENT = accent
    _TRACK = track


FALLBACK_CATALOG: dict = {
    "dark": {"display_name": "Dark", "qss": "dark.qss", "accent": "#6c8cff", "track": "#2b2e37"},
    "light": {"display_name": "Light", "qss": "light.qss", "accent": "#4f6ef7", "track": "#e3e6ec"},
}

FALLBACK_QSS: dict = {
    "dark": "QWidget { background: #15161b; color: #e6e8ee; }",
    "light": "QWidget { background: #f4f5f7; color: #1d2026; }",
}


class ThemeService:
    """Resolves and applies theme stylesheets and palettes."""

    def __init__(self, themes_dir: Path | str | None = None, catalog_path: Path | str | None = None) -> None:
        self.themes_dir = Path(themes_dir) if themes_dir is not None else THEMES_DIR
        self.catalog_path = Path(catalog_path) if catalog_path is not None else THEMES_CATALOG_PATH
        self.catalog: dict = self._load_catalog()

    # -- catalog -----------------------------------------------------------
    def _load_catalog(self) -> dict:
        catalog = json.loads(json.dumps(FALLBACK_CATALOG))  # deep copy
        try:
            if self.catalog_path.exists():
                raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for key, value in raw.items():
                        if isinstance(value, dict) and key in catalog:
                            catalog[key].update(value)
                        elif isinstance(value, dict):
                            catalog[key] = value
            else:
                log.warning("Theme catalog missing at %s; using fallback", self.catalog_path)
        except (json.JSONDecodeError, OSError) as exc:
            log.error("Failed to read theme catalog (%s); using fallback", exc)
        return catalog

    def available_themes(self) -> list[str]:
        return list(self.catalog.keys())

    def display_name(self, key: str) -> str:
        meta = self.catalog.get(key, {})
        return str(meta.get("display_name", key.title()))

    # -- stylesheet --------------------------------------------------------
    def stylesheet(self, theme: str) -> str:
        """Return the QSS for a theme key (falls back gracefully)."""
        qss_file = self.catalog.get(theme, {}).get("qss")
        if qss_file:
            path = self.themes_dir / qss_file
            if path.exists():
                return path.read_text(encoding="utf-8")
            log.warning("QSS file missing for theme %r at %s", theme, path)
        return FALLBACK_QSS.get(theme, FALLBACK_QSS["dark"])

    def apply(self, theme: str, target: QWidget | None = None) -> str:
        """Apply a theme to a widget (default: the whole application)."""
        qss = self.stylesheet(theme)
        meta = self.catalog.get(theme, {})
        set_palette(str(meta.get("accent", _ACCENT)), str(meta.get("track", _TRACK)))
        widget = target or QApplication.instance()
        if widget is not None:
            widget.setStyleSheet(qss)
        log.info("Theme loaded: %s (%s)", theme, self.display_name(theme))
        return qss
