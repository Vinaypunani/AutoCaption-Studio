"""Subtitle preview generation (pure HTML, no Qt — fully testable).

Produces a styled HTML document that shows exactly how captions will look:
dark backdrop, centred caption band, white text, small timestamp. The Queue
page embeds this HTML in a QTextBrowser.
"""

from __future__ import annotations

import html as _html

from .formatter import format_srt_time
from .model import SubtitleCue

_CSS = """
body { margin: 0; padding: 0; background: #000; font-family: Arial, sans-serif; }
.cue { margin: 6px 12px; padding: 4px 10px; border-radius: 3px; }
.cue.selected { outline: 2px solid #4a9eff; background: rgba(255,255,255,0.06); }
.time { color: #9aa3ad; font-size: 11px; margin-bottom: 2px; }
.text { color: #ffffff; font-size: 22px; line-height: 1.3; text-align: center; }
.band { display: inline-block; background: rgba(0,0,0,0.75); padding: 6px 14px; border-radius: 4px; }
"""


def render_cue_html(cue: SubtitleCue, *, show_timestamps: bool = True, selected: bool = False) -> str:
    """Render a single cue as an HTML subtitle band."""
    lines = cue.text.split("\n") if cue.text else [""]
    text_html = "<br>".join(_html.escape(line) for line in lines)
    class_attr = "cue selected" if selected else "cue"
    timestamp = f'<div class="time">{format_srt_time(cue.start)} → {format_srt_time(cue.end)}</div>' if show_timestamps else ""
    return (
        f'<div class="{class_attr}">{timestamp}'
        f'<div class="text"><span class="band">{text_html or "&nbsp;"}</span></div></div>'
    )


def render_preview_html(
    cues: list[SubtitleCue],
    *,
    selected_index: int | None = None,
    show_timestamps: bool = True,
) -> str:
    """Render every cue; ``selected_index`` (cue index) gets a highlight."""
    parts = [_html.escape("<!DOCTYPE html>"), f"<html><head><style>{_CSS}</style></head><body>"]
    for cue in cues:
        parts.append(render_cue_html(cue, show_timestamps=show_timestamps, selected=cue.index == selected_index))
    if not cues:
        parts.append('<div class="time" style="padding:24px">No subtitles to preview yet.</div>')
    parts.append("</body></html>")
    return "\n".join(parts)
