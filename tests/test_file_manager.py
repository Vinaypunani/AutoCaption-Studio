"""FileManager: directory creation, naming, uniqueness, cleanup."""

import os
import time
from pathlib import Path

import pytest

from src.video.file_manager import FileManager


def test_dirs_are_created(tmp_path):
    manager = FileManager(temp_dir=tmp_path)
    assert (tmp_path / "thumbnails").is_dir()
    assert (tmp_path / "audio").is_dir()
    assert (tmp_path / "working").is_dir()


def test_thumbnail_and_audio_paths(file_manager):
    video = Path("C:/videos/my clip.mp4")
    assert file_manager.thumbnail_path(video) == file_manager.thumbnails_dir / "my clip_thumb.jpg"
    assert file_manager.audio_path(video) == file_manager.audio_dir / "my clip_audio.wav"


def test_safe_stem_sanitizes_illegal_characters():
    assert FileManager.safe_stem('a:b\\c*d?e') == "a_b_c_d_e"
    assert FileManager.safe_stem("") == "video"


def test_unique_path_avoids_collisions(tmp_path):
    manager = FileManager(temp_dir=tmp_path)
    first = manager.unique_path(tmp_path, "out.wav")
    first.write_bytes(b"x")
    second = manager.unique_path(tmp_path, "out.wav")
    assert second != first
    assert second.name == "out_1.wav"


def test_cleanup_removes_old_files_only(file_manager, tmp_path):
    old = file_manager.thumbnails_dir / "old.jpg"
    fresh = file_manager.thumbnails_dir / "fresh.jpg"
    old.write_bytes(b"x")
    fresh.write_bytes(b"y")

    past = time.time() - 2 * 3600
    os.utime(old, (past, past))

    removed = file_manager.cleanup_thumbnails(older_than_hours=1)
    assert removed == 1
    assert not old.exists()
    assert fresh.exists()


def test_cleanup_returns_zero_when_empty(file_manager):
    assert file_manager.cleanup_thumbnails(older_than_hours=1) == 0
