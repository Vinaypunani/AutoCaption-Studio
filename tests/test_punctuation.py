"""Punctuation & text cleanup rules."""

from src.subtitles.punctuation import PunctuationCleaner


def _cleaner(**kwargs) -> PunctuationCleaner:
    defaults = dict(
        capitalize_sentences=True,
        normalize_whitespace=True,
        restore_punctuation=True,
        expand_contractions=False,
        remove_fillers=False,
    )
    defaults.update(kwargs)
    return PunctuationCleaner(**defaults)


def test_normalizes_whitespace():
    cleaner = _cleaner()
    assert cleaner.clean("  hello    world  ") == "Hello world."


def test_no_space_before_punctuation():
    cleaner = _cleaner()
    assert cleaner.clean("hello , world") == "Hello, world."


def test_capitalizes_first_letter():
    cleaner = _cleaner()
    assert cleaner.clean("hello there") == "Hello there."


def test_capitalizes_after_sentence_end():
    cleaner = _cleaner()
    assert cleaner.clean("It was great. we loved it") == "It was great. We loved it."


def test_restores_missing_punctuation():
    cleaner = _cleaner()
    assert cleaner.clean("Hello") == "Hello."


def test_does_not_double_punctuate():
    cleaner = _cleaner()
    assert cleaner.clean("Hello!") == "Hello!"
    assert cleaner.clean("Is it good?") == "Is it good?"
    assert cleaner.clean("So true...") == "So true..."


def test_expand_contractions_off_by_default():
    assert _cleaner().clean("don't stop") == "Don't stop."


def test_expand_contractions_on():
    cleaner = _cleaner(expand_contractions=True)
    assert cleaner.clean("don't stop, we're here") == "Do not stop, we are here."


def test_remove_fillers_off_by_default():
    assert _cleaner().clean("um I think so") == "Um I think so."


def test_remove_fillers_on():
    cleaner = _cleaner(remove_fillers=True)
    assert cleaner.clean("um uh I think so") == "I think so."


def test_disabled_returns_text_unchanged():
    cleaner = PunctuationCleaner(enabled=False)
    assert cleaner.clean("  raw  text ") == "  raw  text "


def test_clean_cue_returns_new_cue():
    from src.subtitles.model import SubtitleCue

    cue = SubtitleCue(0.0, 1.0, "hello", index=2)
    cleaned = _cleaner().clean_cue(cue)
    assert cleaned is not cue
    assert cleaned.text == "Hello."
    assert cleaned.index == 2


def test_multilingual_text_passes_through():
    cleaner = _cleaner()
    assert cleaner.clean("مرحبا بالعالم") == "مرحبا بالعالم."
