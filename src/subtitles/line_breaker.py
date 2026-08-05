"""Smart line breaking (Phase 4).

Splits a caption's text into visual lines and, when needed, into multiple
cues — respecting maximum characters per line, maximum lines per cue, phrase
units that should stay together, preferred break points (punctuation,
conjunctions) and a target reading speed.

The result of :meth:`LineBreaker.break_cue` is one or more cues whose time
ranges are distributed proportionally to their character counts.
"""

from __future__ import annotations

import math

from .model import SubtitleCue

# Soft punctuation that marks a *preferred* break point (before/after).
_BREAK_AFTER_PUNCTUATION = frozenset(".,;:!?…")
# Conjunctions and connectors that read better at a line start.
_BREAK_BEFORE_CONJUNCTIONS = frozenset(
    {
        "and", "but", "or", "nor", "so", "yet", "for",
        "because", "although", "though", "while", "whereas",
        "if", "when", "unless", "until", "since", "whereas",
    }
)
# Multi-word phrases that should not be split across lines.
_PHRASES = (
    "in order to", "as well as", "according to", "a lot of",
    "of course", "at least", "at most", "on the other hand",
    "in front of", "in the middle of", "as long as", "even though",
)


class LineBreaker:
    """Splits cue text into lines/cues per the engine options."""

    def __init__(
        self,
        *,
        max_chars_per_line: int = 42,
        max_lines: int = 2,
        keep_phrases: bool = True,
        break_at_punctuation: bool = True,
        break_at_conjunctions: bool = True,
    ) -> None:
        # Note: reading speed is handled by the timing optimizer (dense cues
        # are stretched) and reported by the validator — not by the breaker.
        self.max_chars_per_line = max(1, int(max_chars_per_line))
        self.max_lines = max(1, int(max_lines))
        self.keep_phrases = keep_phrases
        self.break_at_punctuation = break_at_punctuation
        self.break_at_conjunctions = break_at_conjunctions

    # -- public API ---------------------------------------------------------
    def break_cue(self, cue: SubtitleCue) -> list[SubtitleCue]:
        """Return one or more cues with the text split into ≤ max_lines lines."""
        text = " ".join(cue.text.split())
        if not text:
            return [cue]
        if cue.duration <= 0:
            # No timing info — just lay out the lines.
            lines = self._break_lines(text)
            return [self._with_text(cue, "\n".join(lines[: self.max_lines]))]

        lines = self._break_lines(text)
        groups = self._group_lines(lines)
        if self.keep_phrases:
            groups = self._respect_phrases(groups)
        groups = [group for group in groups if group]

        # Distribute the cue's time across the line-groups proportionally to
        # their character counts so multi-cue results never overlap.
        total_chars = sum(len(" ".join(group)) for group in groups) or 1
        result: list[SubtitleCue] = []
        start = cue.start
        for group in groups:
            share = len(" ".join(group)) / total_chars
            end = start + cue.duration * share  # accumulate from the running start
            result.append(self._with_text(cue, "\n".join(group), start=start, end=end))
            start = end
        return result or [cue]

    def break_text(self, text: str) -> list[str]:
        """Line-break plain text (no cue semantics) — convenience for tests."""
        return self._break_lines(text)

    # -- line filling ---------------------------------------------------------
    def _break_lines(self, text: str) -> list[str]:
        words = text.split()
        if not words:
            return [""]
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and len(candidate) > self.max_chars_per_line:
                split_at = self._preferred_break(current)
                lines.append(current[:split_at].strip())
                rest = current[split_at:].strip()
                current = f"{rest} {word}".strip()
            else:
                current = candidate
        if current:
            lines.append(current)
        return self._post_break_phrases(lines) or [text]

    def _preferred_break(self, line: str) -> int:
        """Best split index within ``line`` (keeps left side ≤ max chars)."""
        words = line.split()
        # Start from the last word boundary that fits.
        fit = 0
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) <= self.max_chars_per_line:
                fit = len(candidate)
                current = candidate
            else:
                break

        if fit <= 0:
            return len(line)

        # Prefer a break right AFTER punctuation inside the fitted portion.
        if self.break_at_punctuation:
            for i in range(fit - 1, 0, -1):
                if line[i - 1] in _BREAK_AFTER_PUNCTUATION:
                    return i

        # Prefer a break BEFORE a conjunction that starts a fitted word.
        if self.break_at_conjunctions:
            for word in words:
                if word.strip(".,;:!?…\"'()") in _BREAK_BEFORE_CONJUNCTIONS:
                    at = line.find(word)
                    if 0 < at < fit:
                        return at

        return fit

    def _post_break_phrases(self, lines: list[str]) -> list[str]:
        """Move a phrase-start word that ends a line onto the next line."""
        if not self.keep_phrases or len(lines) < 2:
            return lines
        phrase_starts = {phrase.split()[0] for phrase in _PHRASES}
        result = list(lines)
        for i in range(len(result) - 1):
            current_words = result[i].split()
            if not current_words:
                continue
            last = current_words[-1].strip(".,;:!?…\"'()").lower()
            if last in phrase_starts:
                moved = current_words.pop()
                result[i] = " ".join(current_words)
                result[i + 1] = f"{moved} {result[i + 1]}"
        return [line for line in result if line.strip()]

    # -- grouping ---------------------------------------------------------------
    def _group_lines(self, lines: list[str]) -> list[list[str]]:
        return [lines[i:i + self.max_lines] for i in range(0, len(lines), self.max_lines)]

    def _respect_phrases(self, groups: list[list[str]]) -> list[list[str]]:
        """Move a phrase that straddles two groups entirely into the next."""
        if len(groups) < 2:
            return groups
        merged: list[list[str]] = [list(groups[0])]
        for group in groups[1:]:
            tail = merged[-1]
            if tail and self._phrase_straddles(tail[-1], group[0]):
                tail[-1] = f"{tail[-1]} {group[0]}"
                group = group[1:]
            merged.append(list(group))
        return [g for g in merged if g]

    @staticmethod
    def _phrase_straddles(a: str, b: str) -> bool:
        if not a or not b:
            return False
        a_words = a.split()
        b_words = b.split()
        window = " ".join(a_words[-2:] + b_words[:1])
        return any(phrase in f"{a} {b}" and phrase.startswith(" ".join(a_words[-2:]).lower()) for phrase in _PHRASES)

    # -- helpers ---------------------------------------------------------------
    @staticmethod
    def _with_text(
        cue: SubtitleCue,
        text: str,
        *,
        start: float | None = None,
        end: float | None = None,
    ) -> SubtitleCue:
        """Copy a cue, keeping only the words that fall in the new time range."""
        new_start = cue.start if start is None else start
        new_end = cue.end if end is None else end
        words = [
            word for word in cue.words
            if word.get("end", new_end) >= new_start and word.get("start", new_start) <= new_end
        ]
        return SubtitleCue(
            start=new_start,
            end=new_end,
            text=text,
            index=cue.index,
            words=words,
        )
