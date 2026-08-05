"""Transcription service (Phase 3).

Registers the transcription stage into the job pipeline: given a job whose
audio is ready, it loads the Whisper model (auto-downloading if needed),
transcribes with word timestamps, and stores the result under
``output/transcripts/``. Existing transcripts are reused (cache).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject

from ..ai.whisper.cache import TranscriptStore
from ..ai.whisper.model_manager import ModelManager
from ..ai.whisper.result import TranscriptResult
from ..ai.whisper.settings import WhisperSettings
from ..ai.whisper.transcriber import Transcriber
from ..core.config_manager import ConfigManager
from ..core.logger import get_logger
from ..core.pipeline import PipelineContext, PipelineStage

log = get_logger("transcription_service")


class TranscriptionService(QObject):
    """Adds speech recognition to the job pipeline."""

    def __init__(
        self,
        config: ConfigManager,
        model_manager: Optional[ModelManager] = None,
        transcriber: Optional[Transcriber] = None,
        store: Optional[TranscriptStore] = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.model_manager = model_manager or ModelManager()
        self.transcriber = transcriber or Transcriber()
        self.store = store or TranscriptStore()

    # -- enablement -------------------------------------------------------------
    def enabled(self) -> bool:
        """True when auto-transcription is on AND an engine is importable."""
        settings = WhisperSettings.from_config(self.config)
        if not settings.auto_transcribe:
            return False
        try:
            import faster_whisper  # noqa: F401 - presence check

            return True
        except ImportError:
            log.warning("faster-whisper not installed — transcription disabled")
            return False

    def model_installed(self, name: Optional[str] = None) -> bool:
        settings = WhisperSettings.from_config(self.config)
        return self.model_manager.is_installed(name or settings.model)

    def install_model(self, on_progress=None) -> Path:
        """Ensure the configured model is cached (downloads if needed)."""
        settings = WhisperSettings.from_config(self.config)
        if self.model_manager.is_installed(settings.model):
            return self.model_manager.model_dir(settings.model)
        return self.model_manager.download(settings.model, on_progress=on_progress)

    # -- pipeline integration ------------------------------------------------------
    def stage_runner(self):
        """Return the pipeline callable that performs transcription."""

        def run(ctx: PipelineContext) -> None:
            if ctx.is_cancelled():
                from ..core.pipeline import PipelineCancelledError

                raise PipelineCancelledError("Cancelled before transcription")
            if not ctx.audio_path or not Path(ctx.audio_path).exists():
                from ..core.pipeline import PipelineError

                raise PipelineError("No audio available for transcription")

            settings = WhisperSettings.from_config(self.config)

            # Cache hit — reuse an existing transcript.
            if self.store.exists(ctx.video_path):
                cached = self.store.load(ctx.video_path)
                if cached is not None:
                    ctx.transcript = cached.to_dict()
                    ctx.transcript_path = str(self.store.json_path(ctx.video_path))
                    log.info("Transcript cache hit: %s", ctx.filename)
                    ctx.set_progress(PipelineStage.TRANSCRIPTION_READY, 1.0)
                    return

            result = self.transcriber.transcribe(
                ctx.audio_path,
                settings,
                on_progress=lambda fraction: ctx.set_progress(PipelineStage.TRANSCRIBING, fraction),
                cancel_event=ctx.is_cancelled,
                model_dir=self.model_manager.models_dir,
            )
            ctx.transcript_path = str(self.store.save(result, ctx.video_path))
            ctx.transcript = result.to_dict()
            ctx.set_progress(PipelineStage.TRANSCRIPTION_READY, 1.0)
            log.info("Transcription ready: %s (%d words)", ctx.filename, result.word_count())

        return run
