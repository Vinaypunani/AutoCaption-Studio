"""ASS (Advanced SubStation Alpha) writer — rich styling for renderers."""

from __future__ import annotations

from .formatter import format_ass_time

_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,62,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,0,2,20,20,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _escape(text: str) -> str:
    """Escape ASS override-tag metacharacters in caption text."""
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


class ASSWriter:
    """Plugin: writes a document as ASS with a default caption style."""

    extension = "ass"
    name = "ASS (Advanced SubStation Alpha)"

    def write(self, document, options=None) -> str:  # noqa: D102
        lines = [_HEADER]
        for cue in document.cues:
            text = _escape(cue.text).replace("\n", "\\N")
            lines.append(
                f"Dialogue: 0,{format_ass_time(cue.start)},{format_ass_time(cue.end)},"
                f"Default,,0,0,0,,{text}"
            )
        return "\n".join(lines)
