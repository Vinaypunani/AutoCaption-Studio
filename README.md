# 🎬 AutoCaption Studio

A modern, production-ready **PySide6** desktop application for AI-generated
video captions.

- **Phase 1 — Application Foundation** (tag `v0.1.0-phase1`): polished
  dark/light shell, navigation, settings persistence, logging, job queue.
- **Phase 2 — Video Processing Engine** *(current)*: real video validation,
  metadata extraction, thumbnail generation, audio extraction and in-app
  preview, all through a centralized FFmpeg wrapper.
- **Phase 3+**: Whisper transcription, subtitle generation, export.

**No AI / transcription / subtitle generation exists yet** — Phase 3 plugs
into the service layer.

---

## Quick Start

> ⚠️ **Windows note:** `PySide6-Addons` (QtMultimedia, needed for video
> preview) can fail to install when your Python's `site-packages` path is
> very long (the MS Store Python path typically is). Use a **short-path
> venv** as shown below.

```bash
# 1. Create a virtual environment in a SHORT path (Windows long-path fix)
python -m venv C:/Users/<you>/acstudio-venv

# 2. Install dependencies
C:/Users/<you>/acstudio-venv/Scripts/python -m pip install -r requirements.txt
C:/Users/<you>/acstudio-venv/Scripts/python -m pip install pytest

# 3. Run the app (FFmpeg comes bundled via imageio-ffmpeg)
C:/Users/<you>/acstudio-venv/Scripts/python app.py

# 4. Run the tests (headless — no display needed)
C:/Users/<you>/acstudio-venv/Scripts/python -m pytest
```

On macOS/Linux a venv anywhere works; the app prefers a system
`ffmpeg`/`ffprobe` on PATH, then `FFMPEG_PATH`/`FFPROBE_PATH`, then the
bundled `imageio-ffmpeg` binary.

## Folder Structure

```text
AutoCaptionStudio/
├── app.py                      # Entry point
├── requirements.txt
├── pytest.ini
├── README.md
├── .gitignore
│
├── assets/                     # icons/, fonts/, images/, logo.png
├── config/
│   ├── settings.json           # user settings (auto-created/merged)
│   └── themes.json             # theme catalog (QSS + colors)
├── logs/application.log        # rotating log, created on every start
├── output/                     # export destination (future)
├── temp/
│   ├── thumbnails/             # generated frame previews
│   ├── audio/                  # extracted 16 kHz WAVs (Whisper-ready)
│   └── working/                # scratch space
├── themes/
│   ├── dark.qss
│   └── light.qss
├── src/
│   ├── core/                   # constants, logger, config_manager, app_state
│   ├── models/                 # job_model (Job, stages, sample data)
│   ├── video/                  # ★ Phase 2 engine (see below)
│   ├── services/               # theme_service, video_service (pipeline)
│   ├── widgets/                # sidebar, topbar, drop_zone, progress, queue,
│   │                           # video_info, cards
│   ├── views/                  # home, queue, settings, export, about
│   └── main_window.py          # composition root + frameless window
├── scripts/
│   ├── generate_logo.py
│   └── smoke_run.py            # headless end-to-end verification
└── tests/                      # 91 tests (offscreen Qt + real FFmpeg)
```

### Video engine (`src/video/`)

| Module             | Responsibility                                            |
| ------------------ | --------------------------------------------------------- |
| `ffmpeg_manager.py`| The **only** ffmpeg/ffprobe wrapper: discovery, run, progress |
| `validator.py`     | Extension + file + probe-ability checks, clear errors     |
| `metadata.py`      | `ffprobe` JSON probing (ffmpeg `-i` fallback), `VideoMetadata` |
| `thumbnail.py`     | First meaningful (non-black) frame → `temp/thumbnails/`    |
| `extractor.py`     | Mono 16 kHz WAV extraction → `temp/audio/`                |
| `file_manager.py`  | Temp dirs, safe naming, collision-free paths, cleanup      |
| `preview.py`       | QtMultimedia play / pause / stop / seek widget             |
| `exceptions.py`    | Typed error hierarchy (corrupt, missing audio, no ffmpeg…) |

## Features

### Phase 2 — Video Processing Engine
- **Validation** — only MP4 / MOV / AVI / MKV / WebM / M4V accepted;
  unsupported formats rejected with a clear message.
- **Metadata** — duration, resolution, aspect ratio, FPS, video/audio codec,
  bitrate, channels, file size, creation date → **Video Information** panel.
- **Thumbnails** — automatic, first non-black frame → `temp/thumbnails/`.
- **Audio extraction** — mono 16 kHz WAV (Whisper-ready) → `temp/audio/`.
- **Preview** — play / pause / stop / seek on the Queue page detail panel.
- **Pipeline** — drop a video → Validate → Metadata → Thumbnail → Audio →
  Ready, driven by `VideoService` in a worker thread with live progress.
- **Progress stages** — Waiting · Validating · Reading Metadata · Generating
  Thumbnail · Extracting Audio · Ready · Failed.
- **File manager** — temp/output directories, safe naming, age-based cleanup.
- **Error handling** — corrupt videos, missing audio tracks, missing codecs,
  ffmpeg unavailable, permission errors — all typed, all surfaced in the UI.

### Phase 1 — Application Foundation
- Frameless window with custom title bar, drag-to-move, edge-resize.
- Sidebar navigation: Home, Queue, Settings, Export, About.
- Dark / Light QSS themes (toggle in the top bar).
- JSON settings with defaults merging and corrupt-file recovery.
- Rotating `logs/application.log` + global exception dialog.
- Job queue table with status chips, progress, ETA; sample-data demo.

## Architecture

Light **MVVM-style** layering — Phase 2 added a pipeline without touching
the Phase 1 shell:

```
views (widgets)  →  services (VideoService, ThemeService)  →  video engine
      ↓                          ↓                                  ↓
  AppState (signals)      models (Job)                    FFmpegManager
      ↓
core (config / logging / constants)
```

- **`src/video/`** is pure Python (no Qt) except `preview.py`; everything
  spawns media processes through `FFmpegManager`.
- **`VideoService`** runs one `QThread` worker per job; stage updates flow
  back through signals to `AppState`, which notifies the views.
- Views never touch ffmpeg or files directly.

## Configuration

`config/settings.json` is created on first run and merged with defaults.
Example:

```json
{
    "theme": "dark",
    "language": "English",
    "gpu": true,
    "output_folder": "output",
    "autosave": true,
    "update_channel": "stable",
    "recent_files": [],
    "window": { "width": 1280, "height": 800, "maximized": false }
}
```

Env overrides: `AUTOCAPTION_CONFIG_DIR`, `AUTOCAPTION_THEMES_DIR`,
`AUTOCAPTION_LOGS_DIR`, `FFMPEG_PATH`, `FFPROBE_PATH`.

## Error Handling

Unhandled exceptions are logged and shown as a friendly dialog. Video engine
failures raise typed exceptions (`CorruptedVideoError`,
`MissingAudioTrackError`, `FFmpegNotFoundError`, …) which the pipeline maps
to per-job `error` messages shown in the queue.

## Testing

91 tests: startup, config persistence, navigation, drop-zone, models,
FFmpeg wrapper, validation, metadata, thumbnails, audio extraction, file
manager, pipeline integration (real generated videos), preview and queue UI.

## Roadmap

| Phase | Scope                                                        |
| ----- | ------------------------------------------------------------ |
| 1     | Application foundation *(tagged `v0.1.0-phase1`)*            |
| 2     | Video processing engine *(current, tag next)*                |
| 3     | Whisper transcription & subtitle generation                  |
| 4     | Export pipeline (assemble burned-in captions)                |

## License

MIT — see the About page.
