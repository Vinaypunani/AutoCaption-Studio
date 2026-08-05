"""Normalized JSON writer — the machine-readable export format."""

from __future__ import annotations

import json


class JSONWriter:
    """Plugin: writes the document in the normalized JSON schema."""

    extension = "json"
    name = "JSON (normalized)"

    def write(self, document, options=None) -> str:  # noqa: D102
        return json.dumps(document.to_dict(), indent=2, ensure_ascii=False) + "\n"
