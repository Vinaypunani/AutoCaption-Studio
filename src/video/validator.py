"""Video validation.

Checks, in order:
1. the extension is in the supported set (clear, immediate rejection),
2. the file exists, is a regular file, and is readable,
3. ffmpeg can actually open it (guards against corrupt / fake files).

Each failure raises a typed exception with a user-facing message.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from ..core.constants import SUPPORTED_VIDEO_EXTS
from .exceptions import (
    CorruptedVideoError,
    UnsupportedFormatError,
    VideoValidationError,
)
from .ffmpeg_manager import FFmpegManager

_SUPPORTED_LABEL = ", ".join(sorted(SUPPORTED_VIDEO_EXTS))


def is_supported_extension(path: str | Path) -> bool:
    """True if the path's suffix is in the supported format set."""
    return Path(path).suffix.lower() in SUPPORTED_VIDEO_EXTS


def validate_extension(path: str | Path) -> None:
    """Raise :class:`UnsupportedFormatError` for unsupported extensions."""
    candidate = Path(path)
    if candidate.suffix.lower() not in SUPPORTED_VIDEO_EXTS:
        raise UnsupportedFormatError(str(candidate), _SUPPORTED_LABEL)


def validate_file(path: str | Path) -> None:
    """Raise :class:`VideoValidationError` if the file is unusable."""
    candidate = Path(path)
    if not candidate.exists():
        raise VideoValidationError(f"File not found: {candidate}")
    if not candidate.is_file():
        raise VideoValidationError(f"Not a file: {candidate}")
    if not os.access(candidate, os.R_OK):
        raise VideoValidationError(f"File is not readable (permissions): {candidate}")


def validate_playable(path: str | Path, ffmpeg: FFmpegManager) -> None:
    """Raise :class:`CorruptedVideoError` if ffmpeg cannot open the file."""
    # ``ffmpeg -i`` exits non-zero without an output file, but prints
    # "Input #0" to stderr when the input opens successfully.
    returncode, _, stderr = ffmpeg.run(["-hide_banner", "-i", str(path)])
    if "Input #0" not in stderr:
        detail = stderr.strip().splitlines()[-1] if stderr.strip() else "unrecognised media"
        raise CorruptedVideoError(f"Cannot read video (corrupt or unsupported codec): {detail}", details=stderr)


def validate(path: str | Path, ffmpeg: FFmpegManager, *, probe: bool = True) -> None:
    """Run the full validation chain for a path.

    ``probe=False`` skips the ffmpeg open check (used when a file will be
    probed right after; the pipeline uses the probe result directly).
    """
    validate_extension(path)
    validate_file(path)
    if probe:
        validate_playable(path, ffmpeg)
