"""Subtitle validation (Phase 4).

Checks a cue list for the classic subtitle defects and produces typed
:class:`ValidationIssue` items. :meth:`SubtitleValidator.auto_fix` applies
the mechanically safe corrections (remove empty cues, clamp negative
durations, fix overlaps); reading-speed / line-width problems are reported
as warnings because "fixing" them is a creative decision.
"""

from __future__ import annotations

from dataclasses import dataclass

from .formatter import chars_per_line, reading_speed_cps
from .model import SubtitleCue, reindex


@dataclass
class ValidationIssue:
    """One problem found while validating a document."""

    index: int      # cue index (-1 = document level)
    code: str       # stable machine-readable code
    severity: str   # "error" | "warning"
    message: str

    def __str__(self) -> str:
        where = f"cue #{self.index}: " if self.index >= 0 else ""
        return f"[{self.severity}] {where}{self.message}"

    def to_dict(self) -> dict:
        return {"index": self.index, "code": self.code, "severity": self.severity, "message": self.message}


class SubtitleValidator:
    """Validates cues and optionally auto-fixes mechanical issues."""

    def __init__(
        self,
        *,
        reading_speed_cps: float = 21.0,
        max_chars_per_line: int = 42,
        max_lines: int = 2,
        strictness: str = "balanced",  # lenient | balanced | strict
    ) -> None:
        self.reading_speed_cps = reading_speed_cps
        self.max_chars_per_line = max_chars_per_line
        self.max_lines = max_lines
        self.strictness = strictness

    # -- public API ---------------------------------------------------------
    def validate(self, cues: list[SubtitleCue]) -> list[ValidationIssue]:
        """Return all issues found (sorted by cue index)."""
        issues: list[ValidationIssue] = []
        if not cues:
            issues.append(ValidationIssue(-1, "empty_document", "error", "No subtitles to validate"))
            return issues

        # Adjacency in *time* order (covers every overlapping neighbour once).
        ordered = sorted(enumerate(cues), key=lambda pair: pair[1].start)
        for (_, prev), (pos, cue) in zip(ordered, ordered[1:]):
            if cue.start < prev.end:
                issues.append(
                    ValidationIssue(pos, "overlap", "error",
                                    f"Overlaps previous cue (gap {prev.end - cue.start:+.3f}s)")
                )

        for i, cue in enumerate(cues):
            if cue.is_empty():
                issues.append(ValidationIssue(i, "empty_text", "error", "Caption has no text"))
            if not cue.is_empty():
                cps = reading_speed_cps(cue.text, cue.duration)
                if cps > self.reading_speed_cps:
                    issues.append(
                        ValidationIssue(i, "reading_speed", "warning",
                                        f"Reading speed {cps:.1f} cps exceeds {self.reading_speed_cps:.1f} cps")
                    )
                if chars_per_line(cue.text) > self.max_chars_per_line:
                    issues.append(
                        ValidationIssue(i, "line_too_long", "warning",
                                        f"Line of {chars_per_line(cue.text)} chars exceeds {self.max_chars_per_line}")
                    )
                if cue.line_count > self.max_lines:
                    issues.append(
                        ValidationIssue(i, "too_many_lines", "warning",
                                        f"{cue.line_count} lines exceed max {self.max_lines}")
                    )

        if self.strictness == "lenient":
            issues = [issue for issue in issues if issue.severity == "error"]
        return issues

    def errors(self, cues: list[SubtitleCue]) -> list[ValidationIssue]:
        return [issue for issue in self.validate(cues) if issue.severity == "error"]

    def warnings(self, cues: list[SubtitleCue]) -> list[ValidationIssue]:
        return [issue for issue in self.validate(cues) if issue.severity == "warning"]

    def auto_fix(self, cues: list[SubtitleCue]) -> list[SubtitleCue]:
        """Return a corrected copy: drop empty cues, clamp times, fix overlaps.

        The engine's own pipeline already prevents these mechanical defects
        (empty cues are skipped, the timing optimizer removes overlaps), so
        callers working with *external* cue lists use this."""
        fixed: list[SubtitleCue] = []
        for cue in cues:
            if cue.is_empty():
                continue
            start = max(0.0, cue.start)
            end = max(start, cue.end)
            text = "\n".join(line for line in cue.text.split("\n") if line.strip())
            fixed.append(SubtitleCue(start, end, text, index=cue.index, words=cue.words))
        # Overlap fix.
        result: list[SubtitleCue] = []
        for cue in fixed:
            prev = result[-1] if result else None
            if prev is not None and cue.start < prev.end:
                cue = SubtitleCue(prev.end, max(prev.end, cue.end), cue.text, cue.index, cue.words)
            result.append(cue)
        return reindex(result)

    def is_valid(self, cues: list[SubtitleCue]) -> bool:
        """True when there are no error-severity issues."""
        return not self.errors(cues)
