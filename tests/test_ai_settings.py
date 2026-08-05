"""Whisper transcription settings: config round-trip, validation, device resolution."""

import pytest

from src.ai.whisper.exceptions import UnsupportedLanguageError
from src.ai.whisper.settings import (
    COMMON_LANGUAGES,
    MODEL_NAMES,
    ComputeType,
    DeviceType,
    LanguageMode,
    WhisperSettings,
)


def test_defaults():
    settings = WhisperSettings()
    assert settings.model == "tiny"
    assert settings.device is DeviceType.AUTO
    assert settings.beam_size == 5
    assert settings.compute_type is ComputeType.DEFAULT
    assert settings.language_mode is LanguageMode.AUTO
    assert settings.auto_transcribe is True


def test_model_names_catalog():
    assert MODEL_NAMES == ("tiny", "base", "small", "medium", "large-v3")
    assert "en" in COMMON_LANGUAGES


def test_from_config_missing_keys_use_defaults(config):
    settings = WhisperSettings.from_config(config)
    assert settings.model == "tiny"
    assert settings.auto_transcribe is True


def test_from_config_reads_values(config):
    config.set(
        "whisper",
        {"model": "small", "device": "cuda", "beam_size": 3, "compute_type": "int8",
         "language_mode": "manual", "language": "fr", "threads": 4, "auto_transcribe": False},
    )
    settings = WhisperSettings.from_config(config)
    assert settings.model == "small"
    assert settings.device is DeviceType.CUDA
    assert settings.beam_size == 3
    assert settings.compute_type is ComputeType.INT8
    assert settings.language_mode is LanguageMode.MANUAL
    assert settings.language == "fr"
    assert settings.threads == 4
    assert settings.auto_transcribe is False


def test_to_dict_and_save_to_config(config):
    settings = WhisperSettings(model="base", auto_transcribe=False)
    data = settings.to_dict()
    assert data["model"] == "base"
    assert data["auto_transcribe"] is False

    settings.save_to_config(config)
    assert config.get("whisper")["model"] == "base"
    assert WhisperSettings.from_config(config) == settings


def test_validate_unknown_model():
    with pytest.raises(ValueError, match="Unknown model"):
        WhisperSettings(model="giganto").validate()


def test_validate_beam_size_range():
    with pytest.raises(ValueError, match="beam_size"):
        WhisperSettings(beam_size=0).validate()
    with pytest.raises(ValueError, match="beam_size"):
        WhisperSettings(beam_size=21).validate()
    WhisperSettings(beam_size=1).validate()
    WhisperSettings(beam_size=20).validate()


def test_validate_negative_threads():
    with pytest.raises(ValueError, match="threads"):
        WhisperSettings(threads=-1).validate()


def test_validate_manual_language_short_code():
    with pytest.raises(UnsupportedLanguageError):
        WhisperSettings(language_mode=LanguageMode.MANUAL, language="x").validate()


def test_resolved_device_auto():
    assert WhisperSettings(device=DeviceType.AUTO).resolved_device("cpu") == "cpu"
    assert WhisperSettings(device=DeviceType.AUTO).resolved_device("cuda") == "cuda"
    assert WhisperSettings(device=DeviceType.AUTO).resolved_device("weird") == "cpu"


def test_resolved_device_explicit():
    assert WhisperSettings(device=DeviceType.CPU).resolved_device("cuda") == "cpu"
    assert WhisperSettings(device=DeviceType.CUDA).resolved_device("cpu") == "cuda"
    assert WhisperSettings(device=DeviceType.DIRECTML).resolved_device("cpu") == "directml"
    assert WhisperSettings(device=DeviceType.METAL).resolved_device("cpu") == "metal"
