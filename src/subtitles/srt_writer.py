"""SRT (SubRip) writer — the most widely compatible subtitle format."""

from __future__ import annotations

from .formatter import format_srt_time


class SRTWriter:
    """Plugin: writes a document as SubRip text."""

    extension = "srt"
    name = "SRT (SubRip)"

    def write(self, document, options=None) -> str:  # noqa: D102
        blocks: list[str] = []
        for cue in document.cues:
            blocks.append(
                f"{cue.index}\n{format_srt_time(cue.start)} --> {format_srt_time(cue.end)}\n{cue.text}"
            )
        return "\n\n".join(blocks) + ("\n" if blocks else "")
