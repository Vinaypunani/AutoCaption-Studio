"""Headless smoke run for AutoCaption Studio (Phase 2).

Boots the complete application offscreen, runs the real media pipeline on a
generated test video (validate → metadata → thumbnail → audio), exercises
navigation and theme switching, and writes preview images to
``output/preview_*.png``.

Usage:  python scripts/smoke_run.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Isolate this run's config/logs so the shipped defaults stay pristine.
_SMOKE_ROOT = Path(os.environ.get("SMOKE_ROOT", Path(__file__).resolve().parents[1] / "temp" / "smoke"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["AUTOCAPTION_CONFIG_DIR"] = str(_SMOKE_ROOT / "config")
os.environ["AUTOCAPTION_LOGS_DIR"] = str(_SMOKE_ROOT / "logs")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from src.core.app_state import AppState  # noqa: E402
from src.core.config_manager import ConfigManager  # noqa: E402
from src.core.constants import APP_NAME, LOG_FILE_PATH, OUTPUT_DIR  # noqa: E402
from src.core.logger import get_logger, setup_logging  # noqa: E402
from src.main_window import MainWindow  # noqa: E402
from src.models.job_model import Job, JobStatus  # noqa: E402
from src.services.theme_service import ThemeService  # noqa: E402
from src.services.video_service import VideoService  # noqa: E402
from src.video import FFmpegManager, FileManager  # noqa: E402

PAGES = ["home", "queue", "settings", "export", "about"]


def _make_sample_video(ffmpeg: FFmpegManager, out: Path) -> Path:
    args = [
        "-y", "-f", "lavfi", "-i", "testsrc2=duration=2:size=640x360:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out),
    ]
    rc, _, err = ffmpeg.run(args)
    if rc != 0:
        rc, _, err = ffmpeg.run([
            "-y", "-f", "lavfi", "-i", "testsrc2=duration=2:size=640x360:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-shortest", "-c:v", "mpeg4", "-q:v", "5", "-c:a", "aac", str(out),
        ])
    assert rc == 0 and out.exists(), f"could not create sample video: {err[-300:]}"
    return out


def main() -> int:
    logger = setup_logging()
    logger.info("Smoke run starting (%s)", APP_NAME)

    app = QApplication(sys.argv)

    config = ConfigManager()
    app_state = AppState(config)
    theme_service = ThemeService()
    ffmpeg = FFmpegManager()
    file_manager = FileManager()
    video_service = VideoService(app_state, ffmpeg, file_manager)
    assert video_service.can_process(), "ffmpeg must be available for the smoke run"

    window = MainWindow(config, app_state, theme_service, video_service)
    window.show()
    window.resize(1280, 800)
    app.processEvents()

    # 1) Real end-to-end pipeline: drop a generated video through the UI path.
    sample = _make_sample_video(ffmpeg, _SMOKE_ROOT / "sample.mp4")
    window.pages["home"]._on_files_dropped([str(sample)])

    deadline = time.monotonic() + 60
    job = None
    while time.monotonic() < deadline:
        app.processEvents()
        jobs = app_state.jobs()
        if jobs:
            job = jobs[0]
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                break
        time.sleep(0.05)
    assert job is not None and job.status is JobStatus.COMPLETED, f"pipeline did not finish: {job}"
    assert job.metadata is not None and job.thumbnail_path and job.audio_path
    logger.info("Pipeline finished: metadata=%ss, thumb=%s, audio=%s",
                job.metadata.duration_sec, job.thumbnail_path, job.audio_path)
    logger.info("Pipeline progress: %s (%s)", job.stage.value, job.progress)

    # 2) Navigation through every page (must not raise).
    for page_id in PAGES:
        window.navigate(page_id)
        app.processEvents()
    logger.info("Navigation across all pages OK")

    # 3) Select the processed job on the queue page and render previews.
    window.navigate("queue")
    app.processEvents()
    window.pages["queue"]._on_job_selected(job.job_id)
    app.processEvents()
    window.grab().save(str(OUTPUT_DIR / "preview_queue_phase2.png"))

    window.navigate("home")
    app.processEvents()
    window.grab().save(str(OUTPUT_DIR / "preview_home_phase2.png"))

    app_state.set_theme("light")
    window.navigate("settings")
    app.processEvents()
    window.grab().save(str(OUTPUT_DIR / "preview_settings_light_phase2.png"))

    # Clean shutdown: window.close() stops workers via MainWindow.closeEvent.
    window.close()
    app.processEvents()

    logger.info("Smoke run finished; log file: %s", LOG_FILE_PATH)
    assert LOG_FILE_PATH.exists(), "log file was not created"
    print("smoke run OK — Phase 2 pipeline verified; previews in output/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
