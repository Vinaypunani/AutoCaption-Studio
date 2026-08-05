"""Central FFmpeg wrapper.

The **only** module that spawns ffmpeg/ffprobe processes. Everything else in
the engine (metadata, thumbnails, audio extraction, later phases) goes
through this manager so binary discovery, logging and error handling stay in
one place.

Binary discovery order:
1. explicit path passed to the constructor,
2. ``FFMPEG_PATH`` / ``FFPROBE_PATH`` environment variables,
3. ``ffmpeg`` / ``ffprobe`` on ``PATH``,
4. the binary bundled with ``imageio-ffmpeg`` (ffmpeg only; no ffprobe).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional

from ..core.constants import FFPROBE_ENV_VAR, FFMPEG_ENV_VAR
from ..core.logger import get_logger
from .exceptions import FFmpegExecutionError, FFmpegNotFoundError

log = get_logger("ffmpeg")

# Prevents a console window flashing when ffmpeg runs under the GUI app.
_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

_OUT_TIME_RE = re.compile(r"out_time_us=(\d+)")


def _imageio_ffmpeg_fallback() -> Optional[str]:
    """Return the ffmpeg binary bundled with imageio-ffmpeg, if installed."""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # pragma: no cover - import or lookup failure
        return None


def _resolve_binary(explicit: Optional[str], env_var: str, name: str, fallback: Optional[Callable[[], Optional[str]]]) -> Optional[str]:
    if explicit:
        return str(explicit)
    env = os.environ.get(env_var)
    if env:
        return env
    found = shutil.which(name)
    if found:
        return found
    if fallback is not None:
        return fallback()
    return None


class FFmpegManager:
    """Thin, typed wrapper around ffmpeg/ffprobe subprocesses."""

    def __init__(
        self,
        ffmpeg_path: Optional[str | Path] = None,
        ffprobe_path: Optional[str | Path] = None,
    ) -> None:
        self._ffmpeg = _resolve_binary(ffmpeg_path, FFMPEG_ENV_VAR, "ffmpeg", _imageio_ffmpeg_fallback)
        self._ffprobe = _resolve_binary(ffprobe_path, FFPROBE_ENV_VAR, "ffprobe", None)

    # -- discovery ---------------------------------------------------------
    def _usable(self, binary: Optional[str]) -> bool:
        """A bare command name is assumed resolvable (it came from PATH); an
        absolute path must actually exist on disk."""
        if binary is None:
            return False
        path = Path(binary)
        if path.is_absolute():
            return path.is_file()
        return True

    def available(self) -> bool:
        """True if an ffmpeg binary is usable."""
        return self._usable(self._ffmpeg)

    def has_ffprobe(self) -> bool:
        """True if an ffprobe binary was found (metadata prefers it)."""
        return self._usable(self._ffprobe)

    def ffmpeg_binary(self) -> str:
        if not self.available():
            raise FFmpegNotFoundError(
                "FFmpeg is not available. Install ffmpeg and add it to PATH, "
                "set FFMPEG_PATH, or `pip install imageio-ffmpeg`."
            )
        return self._ffmpeg

    def ffprobe_binary(self) -> str:
        if not self.has_ffprobe():
            raise FFmpegNotFoundError(
                "ffprobe is not available. Install ffmpeg (which ships ffprobe) "
                "or set FFPROBE_PATH."
            )
        return self._ffprobe

    def version(self) -> str:
        """Human-readable ffmpeg version (first line of ``ffmpeg -version``)."""
        _, stdout, _ = self.run(["-version"])
        first = stdout.strip().splitlines()[0] if stdout.strip() else "unknown"
        return first

    # -- low-level execution ------------------------------------------------
    def run(self, args: list[str], timeout: int = 300) -> tuple[int, str, str]:
        """Run ffmpeg and return ``(returncode, stdout, stderr)``. Never raises."""
        command = [self.ffmpeg_binary(), *args]
        log.debug("ffmpeg: %s", " ".join(command))
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=_CREATE_NO_WINDOW,
            )
        except subprocess.TimeoutExpired as exc:  # pragma: no cover - timing dependent
            log.error("ffmpeg timed out after %ss: %s", timeout, " ".join(command))
            raise FFmpegExecutionError(command, "timed out") from exc
        return proc.returncode, proc.stdout, proc.stderr

    def run_checked(self, args: list[str], timeout: int = 300) -> tuple[str, str]:
        """Run ffmpeg and raise :class:`FFmpegExecutionError` on failure."""
        returncode, stdout, stderr = self.run(args, timeout=timeout)
        if returncode != 0:
            log.error("ffmpeg exited %s: %s", returncode, stderr.strip()[-500:])
            raise FFmpegExecutionError([self.ffmpeg_binary(), *args], stderr)
        return stdout, stderr

    def run_probe(self, args: list[str], timeout: int = 120) -> tuple[int, str, str]:
        """Run ffprobe and return ``(returncode, stdout, stderr)``. Never raises."""
        command = [self.ffprobe_binary(), *args]
        log.debug("ffprobe: %s", " ".join(command))
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
        return proc.returncode, proc.stdout, proc.stderr

    # -- progress-aware execution -------------------------------------------
    def run_with_progress(
        self,
        args: list[str],
        duration_sec: Optional[float],
        on_progress: Callable[[float], None],
        timeout: Optional[int] = 600,
    ) -> None:
        """Run ffmpeg with ``-progress pipe:1`` and stream fractions to ``on_progress``.

        ``on_progress`` receives floats in ``[0, 1]`` and is always called
        with ``1.0`` on success. Raises :class:`FFmpegExecutionError` on a
        non-zero exit or timeout; the child process is always terminated on
        any error path (including exceptions raised by ``on_progress``).
        """
        command = [self.ffmpeg_binary(), "-progress", "pipe:1", "-nostats", *args]
        log.debug("ffmpeg (progress): %s", " ".join(command))
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=_CREATE_NO_WINDOW,
        )

        stderr_lines: list[str] = []

        def _drain_stderr() -> None:
            for line in proc.stderr or []:
                stderr_lines.append(line)

        stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
        stderr_thread.start()

        returncode: Optional[int] = None
        try:
            last = 0.0
            for line in proc.stdout or []:
                match = _OUT_TIME_RE.search(line)
                if match and duration_sec and duration_sec > 0:
                    fraction = min(1.0, int(match.group(1)) / (duration_sec * 1_000_000))
                    if fraction > last:
                        last = fraction
                        on_progress(fraction)
            returncode = proc.wait(timeout=timeout)
        except Exception:
            proc.kill()
            try:
                proc.wait(timeout=10)
            except Exception:
                pass
            raise
        finally:
            if proc.stdout:
                proc.stdout.close()

        stderr_thread.join(timeout=5)

        if returncode != 0:
            log.error("ffmpeg exited %s: %s", returncode, "".join(stderr_lines)[-500:])
            raise FFmpegExecutionError(command, "".join(stderr_lines))
        on_progress(1.0)
