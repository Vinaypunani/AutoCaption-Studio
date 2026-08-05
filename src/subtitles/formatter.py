"""Formatting helpers: timestamps per format, reading-speed math.

Pure functions — shared by the writers, the validator and the preview
generator so timing conventions live in exactly one place.
"""

from __future__ import annotations


def _split(seconds: float) -> tuple[int, int, int, int]:
    """Return ``(hours, minutes, seconds, milliseconds)`` for a duration."""
    total_ms = max(0, int(seconds * 1000 + 0.5))  # deterministic half-up
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return hours, minutes, secs, millis


def format_srt_time(seconds: float) -> str:
    """SRT timestamp: ``HH:MM:SS,mmm``."""
    h, m, s, ms = _split(seconds)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_vtt_time(seconds: float) -> str:
    """VTT timestamp: ``HH:MM:SS.mmm``."""
    h, m, s, ms = _split(seconds)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def format_ass_time(seconds: float) -> str:
    """ASS timestamp: ``H:MM:SS.cc`` (centiseconds)."""
    h, m, s, ms = _split(seconds)
    return f"{h}:{m:02d}:{s:02d}.{ms // 10:02d}"


def reading_speed_cps(text: str, duration: float) -> float:
    """Characters-per-second reading speed of a caption (0 when no time)."""
    if duration <= 0:
        return 0.0
    return len(text) / duration


def chars_per_line(text: str) -> int:
    """Width of the widest line in a (possibly multi-line) caption."""
    if not text:
        return 0
    return max(len(line) for line in text.split("\n"))
