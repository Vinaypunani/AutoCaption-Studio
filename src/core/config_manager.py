"""JSON-based configuration manager.

Responsible for loading, validating, persisting and resetting user settings
in ``config/settings.json``. Pure Python (no Qt dependency) so it can be
unit-tested in isolation and reused by CLI/future headless workers.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .constants import DEFAULT_SETTINGS, SETTINGS_PATH
from .logger import get_logger

log = get_logger("config")


class ConfigManager:
    """Load/save application settings as JSON with graceful recovery."""

    def __init__(self, path: Path | str | None = None, defaults: dict[str, Any] | None = None) -> None:
        self.path = Path(path) if path is not None else SETTINGS_PATH
        self.defaults: dict[str, Any] = copy.deepcopy(defaults) if defaults is not None else copy.deepcopy(DEFAULT_SETTINGS)
        self._data: dict[str, Any] = {}
        self.load()

    # -- loading -----------------------------------------------------------
    def load(self) -> dict[str, Any]:
        """Load settings from disk (or create defaults on first run).

        Missing keys are filled from defaults so newly-added settings never
        break an existing user file. A corrupt file is backed up to
        ``settings.json.bak`` and defaults are used instead.
        """
        if not self.path.exists():
            self._data = copy.deepcopy(self.defaults)
            self.save()
            log.info("Created default settings at %s", self.path)
            return self._data

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("settings file root must be a JSON object")
            self._data = self._merge_defaults(raw)
            log.info("Settings loaded from %s", self.path)
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            log.error("Failed to read settings (%s); falling back to defaults", exc)
            try:
                self.path.rename(self.path.with_suffix(".json.bak"))
                log.warning("Backed up unreadable settings to %s", self.path.with_suffix(".json.bak"))
            except OSError:
                pass
            self._data = copy.deepcopy(self.defaults)
            self.save()
        return self._data

    def _merge_defaults(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Deep-merge: nested dicts keep their default keys too."""
        merged = copy.deepcopy(self.defaults)
        for key, value in raw.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key].update(value)
            else:
                merged[key] = value
        return merged

    # -- persistence -------------------------------------------------------
    def save(self) -> None:
        """Write the current settings to disk (creates parent dirs)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, indent=4, ensure_ascii=False), encoding="utf-8"
        )
        log.info("Settings saved to %s", self.path)

    def reset(self) -> None:
        """Restore all settings to their defaults and persist them."""
        self._data = copy.deepcopy(self.defaults)
        self.save()
        log.info("Settings reset to defaults")

    # -- access ------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def as_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)
