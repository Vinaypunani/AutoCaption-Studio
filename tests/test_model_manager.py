"""Whisper model manager: catalog, cache verification, downloads, hardware detection."""

from pathlib import Path

import pytest

from src.ai.whisper.exceptions import CorruptModelError, ModelDownloadError
from src.ai.whisper.model_manager import MODEL_CATALOG, ModelManager, detect_device

_REQUIRED = ("config.json", "model.bin", "tokenizer.json")


@pytest.fixture
def manager(tmp_path) -> ModelManager:
    return ModelManager(models_dir=tmp_path)


def _install_model(manager: ModelManager, name: str, *, model_size: int = 2_000_000) -> None:
    directory = manager.model_dir(name)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text("{}", encoding="utf-8")
    (directory / "model.bin").write_bytes(b"\x00" * model_size)
    (directory / "tokenizer.json").write_text("{}", encoding="utf-8")


def test_catalog_has_all_models():
    assert list(MODEL_CATALOG) == ["tiny", "base", "small", "medium", "large-v3"]
    assert "Systran/faster-whisper-tiny" in MODEL_CATALOG["tiny"]["repo"]


def test_available_models_matches_catalog(manager):
    assert manager.available_models() == list(MODEL_CATALOG)


def test_repo_for_known_and_unknown(manager):
    assert manager.repo_for("tiny") == MODEL_CATALOG["tiny"]["repo"]
    with pytest.raises(ModelDownloadError):
        manager.repo_for("giganto")


def test_is_installed(manager, tmp_path):
    assert not manager.is_installed("tiny")
    _install_model(manager, "tiny")
    assert manager.is_installed("tiny")


def test_is_installed_requires_all_files(manager, tmp_path):
    directory = manager.model_dir("tiny")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text("{}", encoding="utf-8")
    (directory / "model.bin").write_bytes(b"\x00" * 2_000_000)
    assert not manager.is_installed("tiny")  # tokenizer.json missing


def test_verify_integrity(manager):
    assert manager.verify_integrity("tiny") == (False, "model directory missing")
    _install_model(manager, "tiny")
    assert manager.verify_integrity("tiny") == (True, "ok")


def test_verify_integrity_rejects_truncated_model(manager):
    _install_model(manager, "tiny", model_size=10)  # below 1 MB guard
    ok, message = manager.verify_integrity("tiny")
    assert not ok
    assert "model.bin" in message


def test_model_size(manager):
    assert manager.model_size("tiny") == 0
    _install_model(manager, "tiny")
    assert manager.model_size("tiny") > 0


def test_delete_removes_cache(manager):
    _install_model(manager, "tiny")
    assert manager.is_installed("tiny")
    manager.delete("tiny")
    assert not manager.is_installed("tiny")


def test_download_success_reports_progress(manager, monkeypatch):
    def fake_snapshot_download(repo_id, local_dir, **kwargs):
        assert repo_id == MODEL_CATALOG["tiny"]["repo"]
        _install_model(manager, "tiny")
        return str(local_dir)

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)

    progress: list[float] = []
    result = manager.download("tiny", on_progress=progress.append)
    assert result == manager.model_dir("tiny")
    assert progress[-1] == 1.0
    assert manager.is_installed("tiny")


def test_download_failure_raises_model_download_error(manager, monkeypatch):
    def failing_download(repo_id, local_dir, **kwargs):
        raise ConnectionError("no network")

    monkeypatch.setattr("huggingface_hub.snapshot_download", failing_download)
    with pytest.raises(ModelDownloadError):
        manager.download("tiny")


def test_download_detects_incomplete_download(manager, monkeypatch):
    def empty_download(repo_id, local_dir, **kwargs):
        manager.model_dir("tiny").mkdir(parents=True, exist_ok=True)
        return str(local_dir)

    monkeypatch.setattr("huggingface_hub.snapshot_download", empty_download)
    with pytest.raises(CorruptModelError):
        manager.download("tiny")


def test_detect_device_returns_known_value():
    assert detect_device() in ("cpu", "cuda")


def test_model_dir_creates_models_directory(tmp_path):
    manager = ModelManager(models_dir=tmp_path / "nested" / "models")
    assert (tmp_path / "nested" / "models").is_dir()


def test_progress_tqdm_forwards_fractions(monkeypatch):
    """The download progress funnel must survive real tqdm update() calls."""
    from src.ai.whisper.model_manager import _ProgressTqdmFactory

    class _FakeTqdm:
        def __init__(self, *args, **kwargs):
            self.total = kwargs.get("total", 10)
            self.n = 0

        def update(self, n=1):
            self.n += n
            return True

        def close(self):
            pass

    monkeypatch.setattr("tqdm.tqdm", _FakeTqdm)

    progress: list[float] = []
    factory = _ProgressTqdmFactory(progress.append)
    bar = factory(total=10)
    bar.update(5)
    bar.update(2)
    bar.close()

    assert progress == [0.5, 0.7, 1.0]


def test_progress_tqdm_works_without_callback(monkeypatch):
    from src.ai.whisper.model_manager import _ProgressTqdmFactory

    class _FakeTqdm:
        def __init__(self, *args, **kwargs):
            self.total = kwargs.get("total", 10)
            self.n = 0

        def update(self, n=1):
            self.n += n
            return True

        def close(self):
            pass

    monkeypatch.setattr("tqdm.tqdm", _FakeTqdm)
    bar = _ProgressTqdmFactory(None)(total=10)
    bar.update(5)
    bar.close()  # must not raise with no callback
