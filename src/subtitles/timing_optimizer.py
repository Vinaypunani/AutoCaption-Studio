"""Timing optimization (Phase 4).

Post-processes a cue list to produce comfortable, professional timing:

* **overlap correction** — cues never overlap
* **gap insertion** — a minimum gap between consecutive cues
* **merge very short cues** — below ``min_display_duration`` they join the
  previous cue (too short to read)
* **split very long cues** — above ``max_display_duration`` multi-line cues
  are split proportionally across their lines
* **reading-speed stretch** — cues whose text is too dense for the target
  characters-per-second are extended into the following gap
"""

from __future__ import annotations

from .formatter import reading_speed_cps
from .model import SubtitleCue, merge_text, reindex


class TimingOptimizer:
    """Applies the configured timing rules to a list of cues."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        min_display_duration: float = 0.8,
        max_display_duration: float = 7.0,
        min_gap: float = 0.05,
        reading_speed_cps: float = 21.0,
    ) -> None:
        self.enabled = enabled
        self.min_display_duration = max(0.1, float(min_display_duration))
        self.max_display_duration = max(self.min_display_duration + 0.5, float(max_display_duration))
        self.min_gap = max(0.0, float(min_gap))
        self.reading_speed_cps = max(1.0, float(reading_speed_cps))

    # -- public API ---------------------------------------------------------
    def optimize(self, cues: list[SubtitleCue]) -> list[SubtitleCue]:
        """Return a re-timed, re-indexed copy of ``cues``."""
        if not self.enabled or not cues:
            return list(cues)
        result = [self._copy(cue) for cue in cues]
        for _ in range(2):  # a few passes for stability
            result = self._fix_overlaps(result)
            result = self._merge_short(result)
            result = self._split_long(result)
            result = self._insert_gaps(result)
            result = self._extend_for_reading_speed(result)
        return reindex(result)

    # -- passes ---------------------------------------------------------------
    def _fix_overlaps(self, cues: list[SubtitleCue]) -> list[SubtitleCue]:
        result: list[SubtitleCue] = []
        for cue in cues:
            prev = result[-1] if result else None
            if prev is not None and cue.start < prev.end:
                # Move the start after the previous cue, keeping a positive
                # duration (skip the shift when the cue sits fully inside it).
                candidate = min(prev.end + self.min_gap, max(cue.end - 0.01, prev.end))
                if candidate < cue.end:
                    cue = self._copy(cue, start=candidate)
            result.append(cue)
        return result

    def _merge_short(self, cues: list[SubtitleCue]) -> list[SubtitleCue]:
        if not cues:
            return cues
        result: list[SubtitleCue] = []
        for cue in cues:
            if result and cue.duration < self.min_display_duration:
                merged = result[-1]
                result[-1] = self._copy(
                    merged,
                    end=max(merged.end, cue.end),
                    text=merge_text(merged.text, cue.text),
                    words=merged.words + list(cue.words),
                )
            else:
                result.append(self._copy(cue))
        # A leading short cue has nothing to merge into — stretch it instead.
        if result and result[0].duration < self.min_display_duration:
            limit = result[1].start - self.min_gap if len(result) > 1 else result[0].end
            end = min(max(result[0].end, result[0].start + self.min_display_duration), max(limit, result[0].end))
            result[0] = self._copy(result[0], end=end)
        return result

    def _split_long(self, cues: list[SubtitleCue]) -> list[SubtitleCue]:
        result: list[SubtitleCue] = []
        for cue in cues:
            if cue.duration > self.max_display_duration and cue.line_count > 1:
                result.extend(self._split_lines(cue))
            elif cue.duration > self.max_display_duration:
                result.extend(self._split_words(cue))
            else:
                result.append(self._copy(cue))
        return result

    def _insert_gaps(self, cues: list[SubtitleCue]) -> list[SubtitleCue]:
        result: list[SubtitleCue] = []
        for cue in cues:
            prev = result[-1] if result else None
            if prev is not None and cue.start - prev.end < self.min_gap:
                cue = self._copy(cue, start=prev.end + self.min_gap)
            result.append(cue)
        return result

    def _extend_for_reading_speed(self, cues: list[SubtitleCue]) -> list[SubtitleCue]:
        """Extend dense cues into the following gap to meet the CPS target."""
        result = list(cues)
        for i, cue in enumerate(result):
            if cue.is_empty() or cue.duration <= 0:
                continue
            if reading_speed_cps(cue.text, cue.duration) <= self.reading_speed_cps:
                continue
            needed_end = cue.start + len(cue.text) / self.reading_speed_cps
            if i + 1 < len(result):
                new_end = min(needed_end, result[i + 1].start - self.min_gap)
            else:
                new_end = needed_end  # last cue may stay on screen longer
            if new_end > cue.end:
                result[i] = self._copy(cue, end=new_end)
        return result

    # -- splitting -------------------------------------------------------------
    def _split_lines(self, cue: SubtitleCue) -> list[SubtitleCue]:
        lines = [line for line in cue.text.split("\n") if line.strip()]
        total_chars = sum(len(line) for line in lines) or 1
        pieces: list[SubtitleCue] = []
        start = cue.start
        for line in lines:
            share = len(line) / total_chars
            end = start + cue.duration * share
            pieces.append(self._copy(cue, start=start, end=end, text=line))
            start = end
        return pieces

    def _split_words(self, cue: SubtitleCue) -> list[SubtitleCue]:
        """Split a long single-line cue by words, proportionally to length."""
        words = cue.text.split()
        if len(words) < 2:
            return [self._copy(cue)]
        first: list[str] = []
        second: list[str] = []
        for i, word in enumerate(words):
            if i < len(words) // 2:
                first.append(word)
            else:
                second.append(word)
        first_len = sum(len(w) for w in first) or 1
        second_len = sum(len(w) for w in second) or 1
        total = first_len + second_len
        mid = cue.start + cue.duration * (first_len / total)
        return [
            self._copy(cue, start=cue.start, end=mid, text=" ".join(first)),
            self._copy(cue, start=mid, end=cue.end, text=" ".join(second)),
        ]

    # -- helpers ---------------------------------------------------------------
    @staticmethod
    def _copy(cue: SubtitleCue, **changes) -> SubtitleCue:
        values = {"start": cue.start, "end": cue.end, "text": cue.text, "index": cue.index, "words": cue.words}
        values.update(changes)
        start, end = values["start"], values["end"]
        # Keep only the words that fall inside the (possibly re-timed) range.
        values["words"] = [
            word for word in values["words"]
            if word.get("end", end) >= start and word.get("start", start) <= end
        ]
        return SubtitleCue(**values)
