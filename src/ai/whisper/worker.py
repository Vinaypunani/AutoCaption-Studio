"""Standalone transcription worker (QThread).

Used for one-off transcription jobs. The pipeline embeds the same logic via
the transcriber + cancellation callbacks; this worker is the reusable
signal-based wrapper (Preparing → Loading Model → Processing Audio →
Transcribing → Finalizing → Completed).
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from ...core.logger import get_logger
from .exceptions import TranscriptionCancelledError, WhisperError
from .result import TranscriptResult
from .settings import WhisperSettings
from .transcriber import Transcriber

log = get_logger("transcription_worker")

# Stage labels reported through progress_changed.
STAGE_PREPARING = "Preparing"
STAGE_LOADING = "Loading Model"
STAGE_TRANSCRIBING = "Transcribing"
STAGE_FINALIZING = "Finalizing"
STAGE_COMPLETED = "Completed"


class TranscriptionWorker(QThread):
    """Transcribes one audio file off the UI thread."""

    progress_changed = Signal(str, float)  # stage label, overall fraction 0..1
    succeeded = Signal(object)             # TranscriptResult
    failed = Signal(str)                   # error message
    cancelled = Signal()

    def __init__(
        self,
        transcriber: Transcriber,
        audio_path: str | Path,
        settings: WhisperSettings,
        model_dir: Optional[Path | str] = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.transcriber = transcriber
        self.audio_path = str(audio_path)
        self.settings = settings
        self.model_dir = model_dir
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    # -- thread ---------------------------------------------------------------
    def run(self) -> None:
        try:
            self.progress_changed.emit(STAGE_PREPARING, 0.02)
            self.progress_changed.emit(STAGE_LOADING, 0.05)

            def on_progress(fraction: float) -> None:
                self.progress_changed.emit(STAGE_TRANSCRIBING, 0.2 + 0.75 * fraction)

            result = self.transcriber.transcribe(
                self.audio_path,
                self.settings,
                on_progress=on_progress,
                cancel_event=self._cancel.is_set,
                model_dir=self.model_dir,
            )
            self.progress_changed.emit(STAGE_FINALIZING, 0.98)
            self.progress_changed.emit(STAGE_COMPLETED, 1.0)
            log.info("Transcription finished: %s (%d segments)", Path(self.audio_path).name, len(result.segments))
            self.succeeded.emit(result)
        except TranscriptionCancelledError:
            log.info("Transcription cancelled: %s", Path(self.audio_path).name)
            self.cancelled.emit()
        except WhisperError as exc:
            log.error("Transcription failed: %s", exc)
            self.failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("Transcription worker crashed")
            self.failed.emit(f"Unexpected transcription error: {exc}")
