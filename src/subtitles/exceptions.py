"""Exception hierarchy for the subtitle engine (Phase 4)."""

from __future__ import annotations


class SubtitleError(Exception):
    """Base class for all subtitle-generation errors."""


class InvalidCueError(SubtitleError):
    """A cue violates a fundamental invariant (bad times, no text)."""


class UnsupportedFormatError(SubtitleError):
    """A requested output format has no registered writer."""


class EmptySubtitleError(SubtitleError):
    """No cues could be generated (empty transcript, nothing to export)."""
