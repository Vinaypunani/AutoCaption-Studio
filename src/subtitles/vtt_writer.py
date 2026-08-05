"""WebVTT writer — the modern web caption format."""

from __future__ import annotations

from .formatter import format_vtt_time


class VTTWriter:
    """Plugin: writes a document as WebVTT text."""

    extension = "vtt"
    name = "WebVTT"

    def write(self, document, options=None) -> str:  # noqa: D102
        blocks = ["WEBVTT", ""]
        for cue in document.cues:
            blocks.extend(
                [
                    f"{format_vtt_time(cue.start)} --> {format_vtt_time(cue.end)}",
                    cue.text,
                    "",
                ]
            )
        return "\n".join(blocks)
