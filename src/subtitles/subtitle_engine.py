"""Subtitle engine — orchestrates generation and format export.

The engine runs a fixed *build* pipeline (raw cues → punctuation cleanup →
line breaking → timing optimization → validation) and exposes a pluggable
*writer registry* for output formats:

.. code-block:: python

    class SubtitleWriter(Protocol):
        extension: str      # e.g. "srt"
        name: str           # human-readable label
        def write(self, document, options=None) -> str: ...

Adding a new format (TTML, SCC, …) is just ``engine.register_writer(MyWriter())`` —
the engine never needs to change.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..ai.whisper.result import TranscriptResult
from .exceptions import EmptySubtitleError, UnsupportedFormatError
from .line_breaker import LineBreaker
from .model import SubtitleCue, SubtitleDocument, cues_from_transcript, reindex
from .punctuation import PunctuationCleaner
from .settings import SubtitleSettings
from .timing_optimizer import TimingOptimizer
from .validator import SubtitleValidator


@runtime_checkable
class SubtitleWriter(Protocol):
    """Interface every format writer implements (see module docstring)."""

    extension: str
    name: str

    def write(self, document: SubtitleDocument, options=None) -> str: ...


class SubtitleEngine:
    """Generates subtitle documents from transcripts and exports formats."""

    def __init__(
        self,
        writers: Optional[dict[str, SubtitleWriter]] = None,
    ) -> None:
        self._writers: dict[str, SubtitleWriter] = {}
        if writers:
            for writer in writers.values():
                self.register_writer(writer)
        else:
            from .ass_writer import ASSWriter
            from .json_writer import JSONWriter
            from .srt_writer import SRTWriter
            from .txt_writer import TXTWriter
            from .vtt_writer import VTTWriter

            for writer in (SRTWriter(), ASSWriter(), VTTWriter(), JSONWriter(), TXTWriter()):
                self.register_writer(writer)

    # -- writer registry -----------------------------------------------------
    def register_writer(self, writer: SubtitleWriter) -> None:
        """Add a writer plugin for its ``extension``."""
        if not getattr(writer, "extension", None) or not hasattr(writer, "write"):
            raise TypeError(f"{writer!r} is not a valid SubtitleWriter plugin")
        self._writers[writer.extension] = writer

    def writers(self) -> dict[str, SubtitleWriter]:
        return dict(self._writers)

    def available_formats(self) -> list[str]:
        return sorted(self._writers)

    # -- document building -----------------------------------------------------
    def build(self, transcript: TranscriptResult, settings: SubtitleSettings) -> SubtitleDocument:
        """Turn a transcript into a fully processed subtitle document."""
        cues = cues_from_transcript(transcript)
        if not cues:
            raise EmptySubtitleError("Transcript contains no speech to subtitle")

        cleaner = PunctuationCleaner(
            enabled=settings.auto_punctuation,
            capitalize_sentences=settings.capitalize_sentences,
            normalize_whitespace=True,
            restore_punctuation=True,
            expand_contractions=settings.expand_contractions,
            remove_fillers=settings.remove_fillers,
        )
        cleaned = [SubtitleCue(c.start, c.end, cleaner.clean(c.text), index=c.index, words=c.words) for c in cues]

        breaker = LineBreaker(
            max_chars_per_line=settings.max_chars_per_line,
            max_lines=settings.max_lines,
            keep_phrases=settings.keep_phrases,
            break_at_punctuation=settings.break_at_punctuation,
            break_at_conjunctions=settings.break_at_conjunctions,
        )
        broken: list[SubtitleCue] = []
        for cue in cleaned:
            broken.extend(breaker.break_cue(cue))

        timing = TimingOptimizer(
            enabled=settings.timing_optimization,
            min_display_duration=settings.min_display_duration,
            max_display_duration=settings.max_display_duration,
            min_gap=settings.min_gap,
            reading_speed_cps=settings.reading_speed_cps,
        )
        timed = timing.optimize(broken)

        validator = SubtitleValidator(
            reading_speed_cps=settings.reading_speed_cps,
            max_chars_per_line=settings.max_chars_per_line,
            max_lines=settings.max_lines,
            strictness=settings.validation_strictness,
        )
        document = SubtitleDocument.from_transcript(transcript, reindex(timed))
        document.validation_issues = validator.validate(document.cues)
        return document

    # -- export -----------------------------------------------------------------
    def export(self, document: SubtitleDocument, fmt: str, options=None) -> str:
        """Serialize a document in ``fmt`` (raises on unknown formats)."""
        if not document or document.is_empty():
            raise EmptySubtitleError("Nothing to export — the document has no cues")
        writer = self._writers.get(fmt)
        if writer is None:
            raise UnsupportedFormatError(
                f"Unsupported subtitle format {fmt!r}; available: {', '.join(self.available_formats())}"
            )
        return writer.write(document, options)

    def export_all(self, document: SubtitleDocument, options=None) -> dict[str, str]:
        """Serialize in every registered format (``{ext: content}``)."""
        return {ext: self.export(document, ext, options) for ext in self.available_formats()}
