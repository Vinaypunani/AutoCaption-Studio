"""Thumbnail generation.

Extracts a single frame from the video, trying progressively later offsets
so we can skip boring (black / dark) lead-in frames. Brightness is measured
with Pillow when available; without Pillow the first frame wins.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..core.constants import BLACK_FRAME_THRESHOLD, THUMBNAIL_EXT
from .exceptions import ThumbnailGenerationError
from .ffmpeg_manager import FFmpegManager
from .file_manager import FileManager

# Candidate offsets (seconds) tried in order for "first meaningful frame".
_CANDIDATE_OFFSETS = (0.1, 1.0, 2.0, 4.0, 8.0)

_MISSING_PIL = None


def frame_brightness(image_path: str | Path) -> float:
    """Mean luminance (0-255) of a frame image; 255 if it cannot be read.

    ``255`` lets callers treat "can't inspect" as "definitely not black" —
    the frame was already successfully extracted at that point.
    """
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return 255.0
    try:
        with Image.open(image_path) as image:
            gray = image.convert("L")
            return float(ImageStat.Stat(gray).mean[0])
    except Exception:
        return 255.0


def extract_frame(
    ffmpeg: FFmpegManager,
    video_path: str | Path,
    at_seconds: float,
    out_path: str | Path,
) -> Path:
    """Extract a single frame at ``at_seconds`` into ``out_path`` (jpg)."""
    output = Path(out_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg.run_checked(
        [
            "-y",
            "-ss", f"{max(0.0, at_seconds):.2f}",
            "-i", str(video_path),
            "-frames:v", "1",
            "-q:v", "3",
            str(output),
        ]
    )
    return output


def generate_thumbnail(
    ffmpeg: FFmpegManager,
    video_path: str | Path,
    output_dir: str | Path,
    *,
    duration_sec: Optional[float] = None,
    black_threshold: float = BLACK_FRAME_THRESHOLD,
) -> Path:
    """Generate a thumbnail at the first non-black frame.

    Returns the thumbnail path. Raises :class:`ThumbnailGenerationError` if
    no frame can be produced.
    """
    video = Path(video_path)
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    stem = FileManager.safe_stem(video.stem)
    final_path = output_dir_path / f"{stem}_thumb{THUMBNAIL_EXT}"

    offsets = _CANDIDATE_OFFSETS
    if duration_sec:
        # Only try offsets comfortably inside the clip.
        offsets = [t for t in offsets if t < max(0.5, duration_sec - 0.25)]
    if not offsets:
        offsets = (0.1,)

    best_path: Optional[Path] = None
    for index, offset in enumerate(offsets):
        candidate = output_dir_path / f"{stem}_frame_{index}{THUMBNAIL_EXT}"
        try:
            extract_frame(ffmpeg, video, offset, candidate)
        except Exception:
            candidate.unlink(missing_ok=True)
            continue
        if frame_brightness(candidate) >= black_threshold:
            candidate.replace(final_path)
            best_path = final_path
            break
        best_path = candidate  # remember the darkest candidate as a last resort

    if best_path is None:
        raise ThumbnailGenerationError(f"Could not extract any frame from {video}")

    if best_path != final_path:
        best_path.replace(final_path)

    # Clean up any leftover per-candidate frames.
    for leftover in output_dir_path.glob(f"{stem}_frame_*{THUMBNAIL_EXT}"):
        if leftover != final_path:
            leftover.unlink(missing_ok=True)

    return final_path
