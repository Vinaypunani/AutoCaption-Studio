# 🎬 AutoCaption Studio

A modern, production-ready **PySide6** desktop application for AI-generated
video captions. This repository contains **Phase 1 — the application
foundation** only: a polished dark/light shell with navigation, settings
persistence, logging and a job queue. **No AI, transcription, subtitle
generation, FFmpeg or video processing is implemented yet** — later phases
plug into the `services/` layer.

---

## Quick Start

```bash
# 1. Create a virtual environment (Python 3.12+)
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt
pip install pytest              # only needed to run the tests

# 3. Run the app
python app.py

# 4. Run the tests (headless — no display needed)
pytest
```

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
├── output/                     # future export destination
├── temp/                       # future scratch space
├── themes/
│   ├── dark.qss
│   └── light.qss
├── src/
│   ├── core/                   # constants, logger, config_manager, app_state
│   ├── models/                 # job_model (data only)
│   ├── services/               # theme_service (future services plug in here)
│   ├── widgets/                # sidebar, topbar, drop_zone, progress, queue, cards
│   ├── views/                  # home, queue, settings, export, about
│   └── main_window.py          # composition root + frameless window
└── tests/                      # pytest suite (offscreen Qt)
```

## Features (Phase 1)

| Area            | What you get                                                          |
| --------------- | --------------------------------------------------------------------- |
| Shell           | Frameless window with custom title bar, drag-to-move, edge-resize     |
| Navigation      | Sidebar with 5 pages: Home, Queue, Settings, Export, About            |
| Themes          | Dark / Light QSS themes, toggle in the top bar and in Settings        |
| Settings        | Theme, language, GPU, output folder, autosave, update channel → JSON  |
| Drag & Drop     | Accepts video files only (MP4, MKV, MOV, AVI, WebM, …), queues them   |
| Job Queue       | Table with File / Status / Progress / ETA; sample data + demo anim    |
| Progress        | Custom animated progress widget (waiting / running / completed / failed) |
| Logging         | Rotating `logs/application.log`; global exception hook with dialog    |
| Window state    | Size/position remembered across restarts                              |

## Architecture

A light **MVVM-style** separation:

- **Models** (`src/models/`) — pure data (`Job`, `JobStatus`).
- **State / view-model** (`src/core/app_state.py`) — a `QObject` that owns
  the theme, the job queue and recent files, and exposes Qt signals.
  Views subscribe to signals; they never touch files or processing.
- **Services** (`src/services/`) — capabilities behind the UI. Phase 1 ships
  only `ThemeService`; captioning/export services join here later.
- **Views** (`src/views/`) — page widgets; dumb, composable, styled via QSS.
- **Widgets** (`src/widgets/`) — reusable pieces (drop zone, queue, progress).
- **Core** (`src/core/`) — logging, config, constants, shared state.

Dependency direction: `views → widgets/services/models → core`. The UI layer
never implements business logic — a later processing phase can be dropped
into `services/` without touching the shell.

## Configuration

`config/settings.json` is created on first run and merged with defaults so
older files never break. Corrupt files are backed up to
`settings.json.bak`. Example:

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

Environment overrides (used by tests/CI):
`AUTOCAPTION_CONFIG_DIR`, `AUTOCAPTION_THEMES_DIR`, `AUTOCAPTION_LOGS_DIR`.

## Error Handling

Unhandled exceptions are caught by a global hook, written to
`logs/application.log` and surfaced as a friendly *"Unexpected Error — see
logs/application.log"* dialog instead of a silent crash.

## Acceptance Criteria — Phase 1

- [x] Application launches without errors
- [x] Professional dark (and light) UI
- [x] Navigation between all pages works
- [x] Settings persist after restarting the app
- [x] Drag & drop accepts supported video files (no processing)
- [x] Job queue shown with mock data
- [x] Log file created on startup
- [x] UI scales correctly when the window is resized
- [x] Modular, documented, no placeholder AI/video-processing logic

## Roadmap

| Phase | Scope                                        |
| ----- | -------------------------------------------- |
| 1     | Application foundation *(this build)*        |
| 2     | Caption engine, video metadata, FFmpeg hooks |
| 3     | AI transcription & subtitle generation       |
| 4     | Export pipeline (assemble burned-in captions)|

## License

MIT — see the About page.
