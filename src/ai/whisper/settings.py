"""Transcription settings (persisted under ``config/settings.json -> whisper``)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Optional

# Whisper model names supported by the model manager.
MODEL_NAMES: tuple[str, ...] = ("tiny", "base", "small", "medium", "large-v3")

# Common language codes offered in the UI (any Whisper-supported code is
# accepted at runtime).
COMMON_LANGUAGES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ru": "Russian",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "hi": "Hindi",
    "ar": "Arabic",
    "tr": "Turkish",
    "pl": "Polish",
    "uk": "Ukrainian",
}


class DeviceType(str, Enum):
    AUTO = "auto"
    CPU = "cpu"
    CUDA = "cuda"
    DIRECTML = "directml"  # future
    METAL = "metal"  # future


class ComputeType(str, Enum):
    DEFAULT = "default"
    FLOAT16 = "float16"
    INT8 = "int8"
    FLOAT32 = "float32"


class LanguageMode(str, Enum):
    AUTO = "auto"
    MANUAL = "manual"


@dataclass
class WhisperSettings:
    """All knobs for one transcription run."""

    model: str = "tiny"
    device: DeviceType = DeviceType.AUTO
    beam_size: int = 5
    compute_type: ComputeType = ComputeType.DEFAULT
    language_mode: LanguageMode = LanguageMode.AUTO
    language: str = "en"
    threads: int = 0  # 0 = let the engine decide
    auto_transcribe: bool = True

    # -- config integration --------------------------------------------------
    @classmethod
    def from_config(cls, config: Any) -> "WhisperSettings":
        """Build settings from a ConfigManager (missing keys -> defaults)."""
        raw = config.get("whisper", {}) if hasattr(config, "get") else {}
        if not isinstance(raw, dict):
            raw = {}
        return cls(
            model=str(raw.get("model", "tiny")),
            device=DeviceType(str(raw.get("device", "auto"))),
            beam_size=int(raw.get("beam_size", 5)),
            compute_type=ComputeType(str(raw.get("compute_type", "default"))),
            language_mode=LanguageMode(str(raw.get("language_mode", "auto"))),
            language=str(raw.get("language", "en")),
            threads=int(raw.get("threads", 0)),
            auto_transcribe=bool(raw.get("auto_transcribe", True)),
        )

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "device": self.device.value,
            "beam_size": self.beam_size,
            "compute_type": self.compute_type.value,
            "language_mode": self.language_mode.value,
            "language": self.language,
            "threads": self.threads,
            "auto_transcribe": self.auto_transcribe,
        }

    def save_to_config(self, config: Any) -> None:
        config.set("whisper", self.to_dict())

    # -- validation --------------------------------------------------------------
    def validate(self) -> None:
        """Raise :class:`ValueError` on invalid combinations."""
        from .exceptions import UnsupportedLanguageError

        if self.model not in MODEL_NAMES:
            raise ValueError(f"Unknown model {self.model!r}; choose from {', '.join(MODEL_NAMES)}")
        if not 1 <= self.beam_size <= 20:
            raise ValueError("beam_size must be between 1 and 20")
        if self.threads < 0:
            raise ValueError("threads must be >= 0")
        if self.language_mode is LanguageMode.MANUAL and self.language not in COMMON_LANGUAGES:
            # Allow any known code but be strict about obvious typos.
            if len(self.language) != 2:
                raise UnsupportedLanguageError(f"Unsupported language code: {self.language!r}")

    # -- device resolution ---------------------------------------------------------
    def resolved_device(self, detected: str) -> str:
        """Resolve AUTO against a detected device (e.g. ``cpu``/``cuda``)."""
        device = self.device if isinstance(self.device, DeviceType) else DeviceType(str(self.device))
        if device is DeviceType.AUTO:
            return detected if detected in ("cuda", "cpu") else "cpu"
        if device in (DeviceType.DIRECTML, DeviceType.METAL):
            return device.value  # reported as unsupported downstream
        return device.value

    def with_defaults_filled(self, **overrides: Any) -> "WhisperSettings":
        return replace(self, **overrides)
