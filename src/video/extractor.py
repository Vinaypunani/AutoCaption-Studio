"""Audio extraction.

Extracts a mono 16 kHz PCM WAV (Whisper's expected input shape) from a
video. No transcription happens here — Phase 3 feeds these WAVs to the
speech model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from ..core.constants import AUDIO_EXT, AUDIO_SAMPLE_RATE
from .exceptions import (
    AudioExtractionError,
    CorruptedVideoError,
    MissingAudioTrackError,
)
from .ffmpeg_manager import FFmpegManager
from .file_manager import FileManager

# ffmpeg prints this when the output would be empty (e.g. no audio stream).
_NO_STREAM_MARKERS = (
    "does not contain any stream",
    "Output file #0 does not contain any stream",
)


def extract_audio(
    ffmpeg: FFmpegManager,
    video_path: str | Path,
    output_dir: str | Path,
    *,
    duration_sec: Optional[float] = None,
    sample_rate: int = AUDIO_SAMPLE_RATE,
    on_progress: Optional[Callable[[float], None]] = None,
) -> Path:
    """Extract the audio track to ``output_dir/<stem>_audio.wav``.

    Returns the WAV path. Raises :class:`MissingAudioTrackError` when the
    video has no audio stream and :class:`AudioExtractionError` on other
    failures.
    """
    video = Path(video_path)
    if not video.exists():
        raise AudioExtractionError(f"File not found: {video}")

    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    stem = FileManager.safe_stem(video.stem)
    output = output_dir_path / f"{stem}_audio{AUDIO_EXT}"

    args = [
        "-y",
        "-i", str(video),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        str(output),
    ]

    try:
        if on_progress is not None:
            ffmpeg.run_with_progress(args, duration_sec, on_progress)
        else:
            ffmpeg.run_checked(args)
    except Exception as exc:
        stderr = getattr(exc, "details", "") or str(exc)
        output.unlink(missing_ok=True)
        if any(marker in stderr for marker in _NO_STREAM_MARKERS):
            raise MissingAudioTrackError(f"No audio track found in {video.name}") from exc
        if "Invalid data found" in stderr or "No such file" in str(exc):
            raise CorruptedVideoError(f"Cannot read video: {video.name}", details=stderr) from exc
        raise AudioExtractionError(f"Audio extraction failed for {video.name}: {exc}") from exc

    if not output.exists() or output.stat().st_size == 0:
        output.unlink(missing_ok=True)
        raise AudioExtractionError(f"Audio extraction produced no output for {video.name}")

    return output
