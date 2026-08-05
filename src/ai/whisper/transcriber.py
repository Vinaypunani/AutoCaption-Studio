"""Speech-to-text: engine abstraction + faster-whisper backend + chunking.

The engine interface is the seam between the app and the ML dependency:
tests inject a fake engine, the app uses :class:`FasterWhisperEngine`.
Transcription is chunked so the UI gets steady progress and can cancel
between chunks.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable, Optional

from ...core.logger import get_logger
from .exceptions import (
    CUDAUnavailableError,
    EmptyAudioError,
    ModelDownloadError,
    ModelNotFoundError,
    OutOfMemoryError,
    TranscriptionCancelledError,
    TranscriptionError,
)
from .language_detector import LanguageDetector
from .model_manager import detect_device
from .result import Segment, TranscriptResult, Word
from .settings import WhisperSettings

log = get_logger("transcriber")

SAMPLE_RATE = 16_000


class TranscriptionEngine:
    """Duck-typed interface implemented by real and fake backends."""

    def load(self, model_name: str, *, device: str, compute_type: str, threads: int, download_root: Optional[str]) -> None:  # noqa: E501 - protocol
        raise NotImplementedError

    def detect_language(self, audio: Any) -> tuple[str, float]:
        raise NotImplementedError

    def transcribe(
        self,
        audio: Any,
        *,
        language: Optional[str],
        beam_size: int,
        word_timestamps: bool,
    ) -> tuple[str, float, list[Segment]]:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class FasterWhisperEngine(TranscriptionEngine):
    """Real backend powered by faster-whisper (CTranslate2)."""

    def __init__(self) -> None:
        self._model: Any = None
        self._loaded_key: Optional[tuple] = None

    def load(
        self,
        model_name: str,
        *,
        device: str,
        compute_type: str,
        threads: int,
        download_root: Optional[str],
    ) -> None:
        try:
            from faster_whisper import WhisperModel  # deferred: heavy import
        except ImportError as exc:
            raise ModelNotFoundError(
                "faster-whisper is not installed. Run: pip install faster-whisper"
            ) from exc

        if device == "cuda":
            self._check_cuda()

        if compute_type == "default":
            compute_type = "int8" if device == "cpu" else "float16"

        key = (model_name, device, compute_type)
        if self._loaded_key == key and self._model is not None:
            return

        try:
            self._model = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
                cpu_threads=threads or 0,
                download_root=str(download_root) if download_root else None,
            )
            self._loaded_key = key
        except OSError as exc:
            message = str(exc)
            if "Cannot find the file" in message or "No such file" in message:
                raise ModelDownloadError(f"Could not download model {model_name!r}: {message}") from exc
            raise ModelNotFoundError(f"Could not load model {model_name!r}: {message}") from exc
        except RuntimeError as exc:
            if "memory" in str(exc).lower():
                raise OutOfMemoryError(
                    f"Not enough memory for model {model_name!r}. Try a smaller model or int8."
                ) from exc
            raise TranscriptionError(f"Model failed to load: {exc}") from exc

    @staticmethod
    def _check_cuda() -> None:
        try:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() == 0:
                raise CUDAUnavailableError(
                    "CUDA was selected but no GPU was detected. Switch the device to CPU."
                )
        except CUDAUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover
            raise CUDAUnavailableError(f"CUDA check failed: {exc}") from exc

    def detect_language(self, audio: Any) -> tuple[str, float]:
        if self._model is None:
            raise TranscriptionError("Model not loaded")
        language, probability = self._model.detect_language(audio)
        return str(language), float(probability)

    def transcribe(
        self,
        audio: Any,
        *,
        language: Optional[str],
        beam_size: int,
        word_timestamps: bool,
    ) -> tuple[str, float, list[Segment]]:
        if self._model is None:
            raise TranscriptionError("Model not loaded")
        segments_iter, info = self._model.transcribe(
            audio,
            language=language or None,
            beam_size=beam_size,
            word_timestamps=word_timestamps,
        )
        segments: list[Segment] = []
        for segment in segments_iter:
            words = [
                Word(str(word.word), float(word.start), float(word.end), float(word.probability))
                for word in (segment.words or [])
            ]
            segments.append(Segment(float(segment.start), float(segment.end), str(segment.text).strip(), words))
        return str(info.language), float(info.language_probability), segments

    def close(self) -> None:
        self._model = None
        self._loaded_key = None


class Transcriber:
    """Chunked transcription with progress and cancellation."""

    def __init__(
        self,
        engine: Optional[TranscriptionEngine] = None,
        detector: Optional[LanguageDetector] = None,
        chunk_seconds: float = 30.0,
    ) -> None:
        self.engine = engine or FasterWhisperEngine()
        self.detector = detector or LanguageDetector(self.engine)
        self.chunk_seconds = chunk_seconds

    # -- public API ---------------------------------------------------------
    def transcribe(
        self,
        audio_path: str | Path,
        settings: WhisperSettings,
        *,
        on_progress: Optional[Callable[[float], None]] = None,
        cancel_event: Optional[Callable[[], bool]] = None,
        model_dir: Optional[str | Path] = None,
    ) -> TranscriptResult:
        """Transcribe an audio file to a word-timestamped result."""
        samples = self._decode(audio_path)
        duration = len(samples) / SAMPLE_RATE
        if duration < 0.05:
            raise EmptyAudioError(f"Audio contains no usable content ({duration:.2f}s).")
        settings.validate()

        device = settings.resolved_device(detect_device())
        self.engine.load(
            settings.model,
            device=device,
            compute_type=settings.compute_type.value,
            threads=settings.threads,
            download_root=str(model_dir) if model_dir else None,
        )

        language, language_probability = self.detector.resolve(samples, settings)

        chunk_samples = max(1, int(self.chunk_seconds * SAMPLE_RATE))
        total_chunks = max(1, math.ceil(len(samples) / chunk_samples))
        segments: list[Segment] = []
        for index in range(total_chunks):
            if cancel_event is not None and cancel_event():
                raise TranscriptionCancelledError("Transcription cancelled by the user")
            chunk = samples[index * chunk_samples:(index + 1) * chunk_samples]
            if len(chunk) == 0:
                break
            offset = index * chunk_samples / SAMPLE_RATE
            _, _, chunk_segments = self.engine.transcribe(
                chunk,
                language=language,
                beam_size=settings.beam_size,
                word_timestamps=True,
            )
            for segment in chunk_segments:
                segment.start += offset
                segment.end += offset
                for word in segment.words:
                    word.start += offset
                    word.end += offset
                segments.append(segment)
            if on_progress is not None:
                on_progress((index + 1) / total_chunks)

        return TranscriptResult(
            language=language,
            language_probability=language_probability,
            duration=duration,
            segments=segments,
        )

    # -- helpers ---------------------------------------------------------------
    def _decode(self, audio_path: str | Path) -> Any:
        try:
            from faster_whisper.audio import decode_audio
        except ImportError as exc:
            raise ModelNotFoundError("faster-whisper is not installed") from exc
        try:
            return decode_audio(str(audio_path))
        except Exception as exc:
            raise EmptyAudioError(f"Could not decode audio: {exc}") from exc
