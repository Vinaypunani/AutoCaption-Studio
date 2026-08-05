"""Transcript storage (also the results cache).

Writes ``output/transcripts/<video_stem>_<folder-hash>.json`` and
``<...>.txt``. The folder hash keeps same-named videos from different
folders from sharing (and cross-poisoning) a transcript. A stored JSON
doubles as a cache: the pipeline skips re-transcription when a fresh
transcript already exists.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Optional

from ...core.constants import TRANSCRIPTS_DIR
from ...core.logger import get_logger
from .result import TranscriptResult

log = get_logger("transcript_store")


class TranscriptStore:
    """Persists and reloads transcript results for videos."""

    def __init__(self, transcripts_dir: Path | str | None = None) -> None:
        self.transcripts_dir = Path(transcripts_dir) if transcripts_dir is not None else TRANSCRIPTS_DIR
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)

    # -- paths -----------------------------------------------------------------
    @staticmethod
    def _safe_stem(name: str) -> str:
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip()
        return cleaned or "video"

    def _stem_key(self, video_path: str | Path) -> str:
        """Sanitized stem + a short hash of the parent folder (cache key)."""
        source = Path(video_path)
        digest = hashlib.sha1(str(source.resolve().parent).encode("utf-8")).hexdigest()[:8]
        return f"{self._safe_stem(source.stem)}_{digest}"

    def json_path(self, video_path: str | Path) -> Path:
        return self.transcripts_dir / f"{self._stem_key(video_path)}.json"

    def txt_path(self, video_path: str | Path) -> Path:
        return self.transcripts_dir / f"{self._stem_key(video_path)}.txt"

    # -- read --------------------------------------------------------------------
    def exists(self, video_path: str | Path) -> bool:
        return self.json_path(video_path).exists()

    def load(self, video_path: str | Path) -> Optional[TranscriptResult]:
        """Load a stored transcript, or ``None`` when missing/corrupt."""
        path = self.json_path(video_path)
        if not path.exists():
            return None
        try:
            return TranscriptResult.from_json(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            log.warning("Ignoring unreadable transcript %s: %s", path, exc)
            return None

    # -- write --------------------------------------------------------------------
    def save(self, result: TranscriptResult, video_path: str | Path) -> Path:
        """Write JSON + TXT; returns the JSON path."""
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.json_path(video_path)
        tmp_json = json_path.with_suffix(".json.tmp")
        tmp_json.write_text(result.to_json(), encoding="utf-8")
        tmp_json.replace(json_path)

        txt_path = self.txt_path(video_path)
        tmp_txt = txt_path.with_suffix(".txt.tmp")
        tmp_txt.write_text(result.to_txt(), encoding="utf-8")
        tmp_txt.replace(txt_path)

        log.info("Transcript saved: %s (+ %s)", json_path, txt_path.name)
        return json_path

    def delete(self, video_path: str | Path) -> None:
        for path in (self.json_path(video_path), self.txt_path(video_path)):
            path.unlink(missing_ok=True)
