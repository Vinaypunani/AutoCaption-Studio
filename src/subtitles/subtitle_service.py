"""Subtitle service (Phase 4) — pipeline integration + export.

Registers the ``Subtitle Ready`` (generation) and ``Subtitle Validated``
(validation) stages into the job pipeline. Given a job whose transcription
stage has produced ``ctx.transcript``, it builds the subtitle document, saves
every registered format under ``output/subtitles/`` and reports warnings.

Export is available standalone: :meth:`SubtitleService.export` regenerates a
document from a job's transcript and writes the chosen format to any folder.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject

from ..ai.whisper.result import TranscriptResult
from ..core.config_manager import ConfigManager
from ..core.constants import SUBTITLES_DIR
from ..core.logger import get_logger
from ..core.pipeline import PipelineCancelledError, PipelineContext, PipelineError, PipelineStage
from .exceptions import SubtitleError
from .settings import SubtitleSettings
from .subtitle_engine import SubtitleEngine

log = get_logger("subtitle_service")

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class SubtitleService(QObject):
    """Adds subtitle generation/validation/export around the subtitle engine."""

    def __init__(
        self,
        config: ConfigManager,
        engine: Optional[SubtitleEngine] = None,
        subtitles_dir: Optional[Path | str] = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.engine = engine or SubtitleEngine()
        self._subtitles_dir = Path(subtitles_dir) if subtitles_dir is not None else SUBTITLES_DIR

    # -- enablement -------------------------------------------------------------
    def enabled(self) -> bool:
        """True when auto-generation is enabled in settings."""
        return self.settings().auto_generate

    def settings(self) -> SubtitleSettings:
        return SubtitleSettings.from_config(self.config)

    def available_formats(self) -> list[str]:
        return self.engine.available_formats()

    # -- pipeline integration ----------------------------------------------------
    def stage_runner(self):
        """Runner for ``Subtitle Ready``: build + save all formats."""

        def run(ctx: PipelineContext) -> None:
            if ctx.is_cancelled():
                raise PipelineCancelledError("Cancelled before subtitle generation")
            result = self._require_transcript(ctx)
            try:
                document = self.engine.build(result, self.settings())
            except SubtitleError as exc:
                raise PipelineError(f"Subtitle generation failed: {exc}") from exc
            paths = self.save_all(document, ctx.video_path)
            ctx.subtitle_path = str(paths.get(self.settings().default_format, ""))
            ctx.subtitle_formats = {ext: str(path) for ext, path in paths.items()}
            ctx.subtitle_warnings = [str(i) for i in document.validation_issues if i.severity == "warning"]
            log.info("Subtitles ready: %s (%d cues, %d warnings)",
                     ctx.filename, document.cue_count(), len(ctx.subtitle_warnings))
            ctx.set_progress(PipelineStage.SUBTITLE_READY, 1.0)

        return run

    def validation_runner(self):
        """Runner for ``Subtitle Validated``: re-validate; strict mode fails on errors."""

        def run(ctx: PipelineContext) -> None:
            if ctx.is_cancelled():
                raise PipelineCancelledError("Cancelled before subtitle validation")
            result = self._require_transcript(ctx)
            try:
                document = self.engine.build(result, self.settings())
            except SubtitleError as exc:
                raise PipelineError(f"Subtitle validation failed: {exc}") from exc
            issues = document.validation_issues
            ctx.subtitle_warnings = [str(i) for i in issues if i.severity == "warning"]
            errors = [i for i in issues if i.severity == "error"]
            if errors and self.settings().validation_strictness == "strict":
                raise PipelineError("; ".join(str(e) for e in errors[:5]))
            log.info("Subtitles validated: %s (%d warnings)", ctx.filename, len(ctx.subtitle_warnings))
            ctx.set_progress(PipelineStage.SUBTITLE_VALIDATED, 1.0)

        return run

    @staticmethod
    def _require_transcript(ctx: PipelineContext) -> TranscriptResult:
        if not ctx.transcript:
            raise PipelineError("No transcript available — enable transcription first")
        return TranscriptResult.from_dict(ctx.transcript)

    # -- storage ------------------------------------------------------------------
    def subtitles_dir(self) -> Path:
        self._subtitles_dir.mkdir(parents=True, exist_ok=True)
        return self._subtitles_dir

    @staticmethod
    def _stem_key(video_path: str | Path) -> str:
        source = Path(video_path)
        digest = hashlib.sha1(str(source.resolve().parent).encode("utf-8")).hexdigest()[:8]
        stem = _ILLEGAL.sub("_", source.stem).strip() or "video"
        return f"{stem}_{digest}"

    def save_all(self, document, video_path: str | Path) -> dict[str, Path]:
        """Write every registered format to ``output/subtitles/``."""
        directory = self.subtitles_dir()
        contents = self.engine.export_all(document)
        paths: dict[str, Path] = {}
        for ext, content in contents.items():
            path = directory / f"{self._stem_key(video_path)}.{ext}"
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(path)
            paths[ext] = path
        log.info("Saved %d subtitle formats for %s", len(paths), Path(video_path).name)
        return paths

    # -- export --------------------------------------------------------------------
    def export(
        self,
        job,
        fmt: str,
        folder: str | Path,
        *,
        settings: Optional[SubtitleSettings] = None,
    ) -> Path:
        """Regenerate subtitles for ``job`` and write one format into ``folder``."""
        if not job.transcript:
            raise PipelineError(f"Job {job.filename!r} has no transcript — run transcription first")
        result = TranscriptResult.from_dict(job.transcript)
        settings = settings or self.settings()
        document = self.engine.build(result, settings)
        content = self.engine.export(document, fmt)
        out_dir = Path(folder)
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / f"{self._stem_key(job.path)}.{fmt}"
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(target)
        log.info("Exported %s subtitles for %s → %s", fmt, job.filename, target)
        return target
