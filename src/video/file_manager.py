"""File manager: temp directories, output folders, naming and cleanup.

Owns the Phase 2 working tree (``temp/thumbnails``, ``temp/audio``,
``temp/working``) and provides safe, collision-free file naming plus
age-based cleanup for old artifacts.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Iterable, Optional

from ..core.constants import AUDIO_DIR, TEMP_DIR, THUMBNAILS_DIR, WORKING_DIR
from .exceptions import FileOperationError

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class FileManager:
    """Handles temporary files, output folders, cleanup and naming."""

    def __init__(
        self,
        temp_dir: Path | str | None = None,
        thumbnails_dir: Path | str | None = None,
        audio_dir: Path | str | None = None,
        working_dir: Path | str | None = None,
    ) -> None:
        self.temp_dir = Path(temp_dir) if temp_dir is not None else TEMP_DIR
        self.thumbnails_dir = Path(thumbnails_dir) if thumbnails_dir is not None else (self.temp_dir / "thumbnails")
        self.audio_dir = Path(audio_dir) if audio_dir is not None else (self.temp_dir / "audio")
        self.working_dir = Path(working_dir) if working_dir is not None else (self.temp_dir / "working")
        self.ensure_dirs()

    # -- directories ---------------------------------------------------------
    def ensure_dirs(self) -> None:
        """Create all managed directories (idempotent)."""
        for directory in (self.temp_dir, self.thumbnails_dir, self.audio_dir, self.working_dir):
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise FileOperationError(f"Cannot create directory {directory}: {exc}") from exc

    # -- naming ---------------------------------------------------------------
    @staticmethod
    def safe_stem(name: str) -> str:
        """Strip characters that are illegal in file names across platforms."""
        cleaned = _ILLEGAL.sub("_", name).strip()
        return cleaned or "video"

    def thumbnail_path(self, video: Path | str) -> Path:
        """Deterministic thumbnail path for a video file."""
        return self.thumbnails_dir / f"{self.safe_stem(Path(video).stem)}_thumb.jpg"

    def audio_path(self, video: Path | str) -> Path:
        """Deterministic extracted-audio path for a video file."""
        return self.audio_dir / f"{self.safe_stem(Path(video).stem)}_audio.wav"

    def unique_path(self, directory: Path | str, name: str) -> Path:
        """Return ``directory/name``, appending ``_1``, ``_2`` … on collisions."""
        target_dir = Path(directory)
        candidate = target_dir / name
        if not candidate.exists():
            return candidate
        stem = candidate.stem
        suffix = candidate.suffix
        index = 1
        while True:
            candidate = target_dir / f"{stem}_{index}{suffix}"
            if not candidate.exists():
                return candidate
            index += 1

    # -- cleanup ---------------------------------------------------------------
    def cleanup(self, directory: Path | str | None = None, *, older_than_hours: float = 24) -> int:
        """Delete files under ``directory`` (default: all managed dirs) older than N hours.

        Returns the number of files removed. Directories themselves are kept.
        """
        total = 0
        cutoff = time.time() - older_than_hours * 3600
        targets = [Path(directory)] if directory is not None else [
            self.thumbnails_dir, self.audio_dir, self.working_dir,
        ]
        for target_dir in targets:
            if not target_dir.exists():
                continue
            for path in target_dir.iterdir():
                try:
                    if path.is_file() and path.stat().st_mtime < cutoff:
                        path.unlink()
                        total += 1
                except OSError:
                    continue
        return total

    def cleanup_thumbnails(self, *, older_than_hours: float = 24) -> int:
        return self.cleanup(self.thumbnails_dir, older_than_hours=older_than_hours)

    def cleanup_audio(self, *, older_than_hours: float = 24) -> int:
        return self.cleanup(self.audio_dir, older_than_hours=older_than_hours)
