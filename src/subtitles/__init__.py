"""Professional subtitle engine (Phase 4).

Pure-Python subtitle generation: transcript → cue model → line breaking →
punctuation cleanup → timing optimization → validation → writers (SRT / ASS /
VTT / JSON / TXT) behind a plugin ``SubtitleWriter`` interface. The Qt-facing
wrapper (pipeline stages + export) lives in ``subtitle_service.py``; the only
Qt-adjacent module here is ``preview_generator`` (pure HTML, testable).
"""

from __future__ import annotations

from .exceptions import (
    EmptySubtitleError,
    InvalidCueError,
    SubtitleError,
    UnsupportedFormatError,
)
from .model import SubtitleCue, SubtitleDocument
from .subtitle_engine import SubtitleEngine
from .subtitle_service import SubtitleService

__all__ = [
    "EmptySubtitleError",
    "InvalidCueError",
    "SubtitleCue",
    "SubtitleDocument",
    "SubtitleEngine",
    "SubtitleError",
    "SubtitleService",
    "UnsupportedFormatError",
]
