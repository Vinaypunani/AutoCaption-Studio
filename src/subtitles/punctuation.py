"""Punctuation & text cleanup (Phase 4).

Optional, user-configurable rules applied to each caption:

* capitalize sentence starts
* collapse/normalize whitespace
* restore missing ending punctuation
* expand contractions (e.g. ``don't`` → ``do not``)
* remove filler words (``um``, ``uh``, ``er``, …)
"""

from __future__ import annotations

import re

from .model import SubtitleCue

_SENTENCE_END = frozenset(".!?…\"")
_FILLERS = ("um", "uh", "er", "erm", "hmm", "huh", "uhh", "umm")
_CONTRACTIONS = {
    "don't": "do not", "can't": "cannot", "won't": "will not",
    "shouldn't": "should not", "couldn't": "could not", "wouldn't": "would not",
    "isn't": "is not", "aren't": "are not", "wasn't": "was not",
    "weren't": "were not", "didn't": "did not", "doesn't": "does not",
    "haven't": "have not", "hasn't": "has not", "hadn't": "had not",
    "i'm": "I am", "i've": "I have", "i'll": "I will", "i'd": "I would",
    "you're": "you are", "you've": "you have", "you'll": "you will",
    "we're": "we are", "we've": "we have", "we'll": "we will",
    "they're": "they are", "they've": "they have", "they'll": "they will",
    "it's": "it is", "that's": "that is", "there's": "there is",
    "let's": "let us", "he's": "he is", "she's": "she is",
}
_WORD_RE = re.compile(r"\b([A-Za-z]+(?:'[A-Za-z]+)?)\b")


class PunctuationCleaner:
    """Applies the configured cleanup rules to a cue's text."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        capitalize_sentences: bool = True,
        normalize_whitespace: bool = True,
        restore_punctuation: bool = True,
        expand_contractions: bool = False,
        remove_fillers: bool = False,
    ) -> None:
        self.enabled = enabled
        self.capitalize_sentences = capitalize_sentences
        self.normalize_whitespace = normalize_whitespace
        self.restore_punctuation = restore_punctuation
        self.expand_contractions = expand_contractions
        self.remove_fillers = remove_fillers

    # -- public API ---------------------------------------------------------
    def clean(self, text: str) -> str:
        """Apply all enabled rules to a caption's text."""
        if not text or not self.enabled:
            return text
        result = text
        if self.normalize_whitespace:
            result = self._normalize(result)
        if self.remove_fillers:
            result = self._remove_fillers(result)
        if self.expand_contractions:
            result = self._expand(result)
        if self.capitalize_sentences:
            result = self._capitalize(result)
        if self.restore_punctuation:
            result = self._restore_punctuation(result)
        return result

    def clean_cue(self, cue: SubtitleCue) -> SubtitleCue:
        """Return a copy of the cue with cleaned text."""
        from .model import SubtitleCue as _Cue

        return _Cue(cue.start, cue.end, self.clean(cue.text), index=cue.index, words=cue.words)

    # -- rules ---------------------------------------------------------------
    @staticmethod
    def _normalize(text: str) -> str:
        result = re.sub(r"\s+", " ", text)          # collapse all whitespace
        result = re.sub(r"\s+([,.;:!?…])", r"\1", result)  # no space before punctuation
        return result.strip()

    @staticmethod
    def _capitalize(text: str) -> str:
        def fix(match: re.Match) -> str:
            return match.group(0).capitalize()

        result = _WORD_RE.sub(fix, text, count=1)
        result = re.sub(r"([.!?…])\s+([a-z])", lambda m: f"{m.group(1)} {m.group(2).upper()}", result)
        return result

    def _restore_punctuation(self, text: str) -> str:
        stripped = text.rstrip()
        if not stripped:
            return text
        if stripped[-1] in _SENTENCE_END:
            return stripped
        return stripped + "."

    def _expand(self, text: str) -> str:
        def replace(match: re.Match) -> str:
            word = match.group(1).lower()
            return _CONTRACTIONS.get(word, match.group(1))

        return _WORD_RE.sub(replace, text)

    def _remove_fillers(self, text: str) -> str:
        lowered = text.lower()
        kept: list[str] = []
        for word in text.split():
            if word.strip(".,!?;:\"'()") in _FILLERS:
                continue
            kept.append(word)
        result = " ".join(kept)
        return result or text
