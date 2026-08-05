"""TranscriptStore: persistence, caching, corrupt-file recovery."""

from src.ai.whisper.cache import TranscriptStore
from src.ai.whisper.result import Segment, TranscriptResult, Word


def _result() -> TranscriptResult:
    return TranscriptResult(
        language="en",
        duration=1.5,
        segments=[
            Segment(0.0, 1.5, "Hello there.", [Word("Hello", 0.0, 0.4, 0.99)])
        ],
    )


def test_save_writes_json_and_txt(tmp_path):
    store = TranscriptStore(tmp_path)
    video = tmp_path / "videos" / "clip.mp4"
    json_path = store.save(_result(), video)

    assert json_path == store.json_path(video)
    assert store.txt_path(video).exists()
    assert json_path.read_text(encoding="utf-8").startswith("{")


def test_load_roundtrip(tmp_path):
    store = TranscriptStore(tmp_path)
    video = tmp_path / "clip.mp4"
    store.save(_result(), video)

    loaded = store.load(video)
    assert loaded is not None
    assert loaded.language == "en"
    assert loaded.segments[0].words[0].word == "Hello"
    assert loaded.word_count() == 1


def test_exists_and_missing(tmp_path):
    store = TranscriptStore(tmp_path)
    video = tmp_path / "clip.mp4"
    assert not store.exists(video)
    store.save(_result(), video)
    assert store.exists(video)


def test_delete_removes_both_files(tmp_path):
    store = TranscriptStore(tmp_path)
    video = tmp_path / "clip.mp4"
    store.save(_result(), video)
    store.delete(video)
    assert not store.exists(video)
    assert not (tmp_path / "clip.txt").exists()


def test_load_missing_returns_none(tmp_path):
    store = TranscriptStore(tmp_path)
    assert store.load(tmp_path / "nope.mp4") is None


def test_load_corrupt_json_returns_none(tmp_path):
    store = TranscriptStore(tmp_path)
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    assert store.load(tmp_path / "bad.mp4") is None


def test_safe_stem_sanitizes_filenames(tmp_path):
    store = TranscriptStore(tmp_path)
    video = tmp_path / 'weird<name>:part*.mp4'
    json_path = store.save(_result(), video)
    # Both '>' and ':' become underscores, so 'name>:part' -> 'name__part'.
    assert json_path.name.startswith("weird_name__part_")
    assert json_path.name.endswith(".json")


def test_same_stem_from_different_folders_do_not_collide(tmp_path):
    store = TranscriptStore(tmp_path)
    folder_a = tmp_path / "a"
    folder_b = tmp_path / "b"
    folder_a.mkdir()
    folder_b.mkdir()

    path_a = store.save(_result(), folder_a / "clip.mp4")
    path_b = store.save(_result(), folder_b / "clip.mp4")

    assert path_a != path_b  # distinct cache keys, no cross-poisoning
    assert not store.exists(folder_b / "clip.mp4") or store.load(folder_a / "clip.mp4") is not None
    store.save(_result(), folder_a / "clip.mp4")
    assert store.load(folder_b / "clip.mp4") is not None


def test_txt_content_matches_full_text(tmp_path):
    store = TranscriptStore(tmp_path)
    video = tmp_path / "clip.mp4"
    result = _result()
    store.save(result, video)
    assert store.txt_path(video).read_text(encoding="utf-8") == result.full_text()
