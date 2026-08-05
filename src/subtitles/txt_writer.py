"""Plain-text writer — captions as readable text (one line per line)."""

from __future__ import annotations


class TXTWriter:
    """Plugin: writes each cue's text, blank line between cues."""

    extension = "txt"
    name = "Plain Text"

    def write(self, document, options=None) -> str:  # noqa: D102
        blocks = [cue.text for cue in document.cues if cue.text.strip()]
        return "\n\n".join(blocks) + ("\n" if blocks else "")
