"""Whisper model manager.

Manages the on-disk model cache (``models/<name>/``): listing, detection,
integrity verification, size, deletion and progressive downloads from
Hugging Face. Also exposes hardware detection (CUDA vs CPU).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Optional

from ...core.constants import MODELS_DIR
from ...core.logger import get_logger
from .exceptions import CorruptModelError, ModelDownloadError

log = get_logger("model_manager")

# name -> (HF repo id, approx. size hint in GB)
MODEL_CATALOG: dict[str, dict] = {
    "tiny": {"repo": "Systran/faster-whisper-tiny", "size_hint_gb": 0.075},
    "base": {"repo": "Systran/faster-whisper-base", "size_hint_gb": 0.145},
    "small": {"repo": "Systran/faster-whisper-small", "size_hint_gb": 0.46},
    "medium": {"repo": "Systran/faster-whisper-medium", "size_hint_gb": 1.5},
    "large-v3": {"repo": "Systran/faster-whisper-large-v3", "size_hint_gb": 2.9},
}

# Files that must be present (and non-trivial) for a model to be usable.
_REQUIRED_FILES = ("config.json", "model.bin", "tokenizer.json")
_MIN_MODEL_BIN_BYTES = 1_000_000  # 1 MB — guards against empty/truncated files


def detect_device() -> str:
    """Return ``cuda`` when a CUDA device is available, else ``cpu``."""
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:  # pragma: no cover - import/runtime failure
        pass
    return "cpu"


class ModelManager:
    """Owns the model cache directory."""

    def __init__(self, models_dir: Path | str | None = None) -> None:
        self.models_dir = Path(models_dir) if models_dir is not None else MODELS_DIR
        self.models_dir.mkdir(parents=True, exist_ok=True)

    # -- catalog ------------------------------------------------------------
    def available_models(self) -> list[str]:
        return list(MODEL_CATALOG)

    def repo_for(self, name: str) -> str:
        if name not in MODEL_CATALOG:
            raise ModelDownloadError(f"Unknown model {name!r}")
        return MODEL_CATALOG[name]["repo"]

    # -- cache --------------------------------------------------------------
    def model_dir(self, name: str) -> Path:
        return self.models_dir / name

    def is_installed(self, name: str) -> bool:
        return self.model_dir(name).exists() and all(
            (self.model_dir(name) / file).is_file() for file in _REQUIRED_FILES
        )

    def verify_integrity(self, name: str) -> tuple[bool, str]:
        """Return ``(ok, message)`` — checks required files and sizes."""
        directory = self.model_dir(name)
        if not directory.exists():
            return False, "model directory missing"
        for file in _REQUIRED_FILES:
            path = directory / file
            if not path.is_file():
                return False, f"missing {file}"
        model_bin = directory / "model.bin"
        if model_bin.stat().st_size < _MIN_MODEL_BIN_BYTES:
            return False, "model.bin too small (truncated download?)"
        return True, "ok"

    def model_size(self, name: str) -> int:
        """Total cache size for a model in bytes (0 if absent)."""
        directory = self.model_dir(name)
        if not directory.exists():
            return 0
        return sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())

    def delete(self, name: str) -> None:
        directory = self.model_dir(name)
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)
            log.info("Deleted model cache: %s", directory)

    # -- download -------------------------------------------------------------
    def download(
        self,
        name: str,
        on_progress: Optional[Callable[[float], None]] = None,
    ) -> Path:
        """Download a model into the cache, reporting fractions (0..1)."""
        repo = self.repo_for(name)
        target = self.model_dir(name)
        target.mkdir(parents=True, exist_ok=True)
        log.info("Downloading model %s from %s", name, repo)
        try:
            from huggingface_hub import snapshot_download

            snapshot_download(
                repo_id=repo,
                local_dir=str(target),
                tqdm_class=_ProgressTqdmFactory(on_progress),
            )
        except TypeError:
            # Very old huggingface_hub without tqdm_class support.
            from huggingface_hub import snapshot_download

            snapshot_download(repo_id=repo, local_dir=str(target))
        except Exception as exc:  # network / disk / hub failures
            log.error("Model download failed (%s): %s", name, exc)
            raise ModelDownloadError(f"Failed to download model {name!r}: {exc}") from exc

        ok, message = self.verify_integrity(name)
        if not ok:
            raise CorruptModelError(f"Downloaded model {name!r} is incomplete: {message}")
        if on_progress is not None:
            on_progress(1.0)
        return target


class _ProgressTqdmFactory:
    """Returns a ``tqdm`` subclass that forwards progress to a callback."""

    def __init__(self, callback: Optional[Callable[[float], None]]) -> None:
        self._callback = callback

    def __call__(self, *args, **kwargs):  # noqa: ANN002, ANN003 - passthrough
        try:
            from tqdm import tqdm as _tqdm  # deferred: optional dependency
        except ImportError:  # pragma: no cover
            return None

        class _ProgressTqdm(_tqdm):
            def __init__(self, *args, **kwargs):  # noqa: D102
                self._callback = kwargs.pop("callback", None)
                super().__init__(*args, **kwargs)

            def update(self, n=1) -> Optional[bool]:  # noqa: D102
                result = super().update(n)
                if self.total and self._callback:
                    self._callback(min(1.0, self.n / self.total))
                return result

            def close(self) -> None:  # noqa: D102
                if self._callback:
                    self._callback(1.0)
                super().close()

        kwargs["callback"] = self._callback
        return _ProgressTqdm(*args, **kwargs)
