# 🎬 AutoCaption Studio

A modern, production-ready **PySide6** desktop application for AI-generated
video captions.

- **Phase 1 — Application Foundation** (tag `v0.1.0-phase1`): polished
  dark/light shell, navigation, settings persistence, logging, job queue.
- **Phase 2 — Video Processing Engine** (tag `v0.2.0-phase2`): real video
  validation, metadata, thumbnails, audio extraction and preview through a
  centralized FFmpeg wrapper.
- **Phase 3 — AI Speech Recognition** *(current)*: Whisper transcription
  with word-level timestamps, model management, hardware detection and
  results storage.
- **Phase 4+**: subtitle generation (SRT/ASS, karaoke), rendering, export.

**Subtitle generation / rendering / export do not exist yet** — Phase 4
plugs into the pipeline's `Subtitle Ready` / `Render Ready` stages.

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

**Whisper models:** the first transcription automatically downloads the
configured model (default `tiny`) from Hugging Face into `models/` (progress
is reported through the pipeline). Choose a model under
*Settings → AI / Transcription*.

## Folder Structure

```text
AutoCaptionStudio/
├── app.py                      # Entry point
├── requirements.txt
├── README.md
├── .gitignore
│
├── assets/                     # icons/, fonts/, images/, logo.png
├── config/
│   ├── settings.json           # user settings (auto-created/merged)
│   └── themes.json             # theme catalog (QSS + colors)
├── logs/application.log        # rotating log, created on every start
├── output/
│   └── transcripts/            # ★ per-video JSON + TXT transcripts
├── temp/
│   ├── thumbnails/             # generated frame previews
│   ├── audio/                  # extracted 16 kHz WAVs (Whisper-ready)
│   └── working/                # scratch space
├── models/                     # ★ Whisper model cache (auto-downloaded)
├── themes/
│   ├── dark.qss
│   └── light.qss
├── src/
│   ├── core/                   # constants, logger, config_manager, app_state
│   │   └── pipeline.py         # ★ job pipeline: ordered stages + runners
│   ├── models/                 # job_model (Job, stages, sample data)
│   ├── video/                  # Phase 2 engine (see below)
│   ├── ai/whisper/             # ★ Phase 3 engine (see below)
│   ├── services/               # theme_service, video_service (pipeline),
│   │                           # transcription_service (AI stage)
│   ├── widgets/                # sidebar, topbar, drop_zone, progress, queue,
│   │                           # video_info, cards
│   ├── views/                  # home, queue, settings, export, about
│   └── main_window.py          # composition root + frameless window
├── scripts/
│   ├── generate_logo.py
│   └── smoke_run.py            # headless end-to-end verification
├── .github/workflows/tests.yml # ★ CI: full suite on push/PR
└── tests/                      # 183 tests (offscreen Qt + real FFmpeg)
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

### AI engine (`src/ai/whisper/`)

| Module              | Responsibility                                          |
| ------------------- | ------------------------------------------------------- |
| `model_manager.py`  | Model catalog (tiny→large-v3), cache, download w/ progress, integrity, delete |
| `settings.py`       | `WhisperSettings`: model, device, beam, compute, language, threads |
| `transcriber.py`    | Engine protocol + faster-whisper backend, chunked runs, cancel, progress |
| `language_detector.py` | Auto detection vs manual selection, confidence        |
| `result.py`         | `TranscriptResult`/`Segment`/`Word` with timestamps + confidence |
| `cache.py`          | `output/transcripts/` storage (JSON+TXT, also a cache)  |
| `worker.py`         | Standalone QThread wrapper (Preparing → … → Completed)  |
| `exceptions.py`     | Typed errors: download, CUDA, OOM, empty audio, cancel… |

## Features

### Phase 3 — AI Speech Recognition
- **Transcription** — Whisper (faster-whisper / CTranslate2) with
  **word-level timestamps and confidence** for every word (drives karaoke
  highlighting in Phase 4).
- **Model manager** — tiny / base / small / medium / large-v3; automatic
  download with progress, integrity verification, size, delete.
- **Hardware detection** — auto-detects CUDA vs CPU (manual override in
  Settings; DirectML / Metal reserved).
- **Language detection** — auto-detect with confidence, or manual language.
- **Queue integration** — after audio extraction the pipeline runs the
  `Transcription Ready` stage automatically (toggle in Settings), stores
  `output/transcripts/<video>_<folder>.json` + `.txt`, and shows a transcript
  summary with an *Open Transcript* button on the Queue page.
- **Cancellation** — cancel a job between stages, or cancel transcription
  between chunks.
- **Results cache** — re-processing a video reuses its stored transcript.
- **Error handling** — model download failure, CUDA unavailable, OOM, corrupt
  model, unsupported language, empty audio, user cancellation — all typed
  and surfaced per job.
- **Job pipeline** (`src/core/pipeline.py`) — ordered stages
  (`Imported → Validated → Metadata Ready → Thumbnail Ready → Audio Ready →
  Transcription Ready → Subtitle Ready → Render Ready → Completed`) with
  per-stage progress weights; later phases register new stage runners.

### Phase 2 — Video Processing Engine
- **Validation** — only MP4 / MOV / AVI / MKV / WebM / M4V accepted;
  unsupported formats rejected with a clear message.
- **Metadata** — duration, resolution, aspect ratio, FPS, video/audio codec,
  bitrate, channels, file size, creation date → **Video Information** panel.
- **Thumbnails** — automatic, first non-black frame → `temp/thumbnails/`.
- **Audio extraction** — mono 16 kHz WAV (Whisper-ready) → `temp/audio/`.
- **Preview** — play / pause / stop / seek on the Queue page detail panel.
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

Light **MVVM-style** layering — each phase adds capabilities without
touching the earlier shell:

```
views (widgets)  →  services  →  engines (video / ai) → external tools
      ↓                ↓                 ↓
  AppState         Pipeline         FFmpegManager / faster-whisper
  (signals)    (core/pipeline.py)
      ↓
core (config / logging / constants)
```

- **`src/video/`** is pure Python (no Qt) except `preview.py`; everything
  spawns media processes through `FFmpegManager`.
- **`src/ai/whisper/`** isolates the ML dependency behind an engine
  protocol — tests inject a fake engine, the app uses faster-whisper.
- **`VideoService`** runs one `QThread` worker per job; stage updates flow
  back through signals to `AppState`, which notifies the views.
- **`TranscriptionService`** registers the transcription stage runner into
  the same pipeline — retries, cancellations and future stages
  (translation, speaker diarization, emoji) hang off the same structure.
- Views never touch ffmpeg, files or models directly.

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
    "window": { "width": 1280, "height": 800, "maximized": false },
    "whisper": {
        "model": "tiny",
        "device": "auto",
        "beam_size": 5,
        "compute_type": "default",
        "language_mode": "auto",
        "language": "en",
        "threads": 0,
        "auto_transcribe": true
    }
}
```

Env overrides: `AUTOCAPTION_CONFIG_DIR`, `AUTOCAPTION_THEMES_DIR`,
`AUTOCAPTION_LOGS_DIR`, `FFMPEG_PATH`, `FFPROBE_PATH`.

## Error Handling

Unhandled exceptions are logged and shown as a friendly dialog. Video engine
failures raise typed exceptions (`CorruptedVideoError`,
`MissingAudioTrackError`, `FFmpegNotFoundError`, …) and AI failures raise
`WhisperError` subclasses (`ModelDownloadError`, `CUDAUnavailableError`,
`OutOfMemoryError`, `EmptyAudioError`, …) — the pipeline maps both to
per-job `error` messages shown in the queue.

## Testing

183 tests: startup, config persistence, navigation, drop-zone, models,
FFmpeg wrapper, validation, metadata, thumbnails, audio extraction, file
manager, pipeline integration (real generated videos), **job pipeline
(stages, progress weights, cancellation), AI result/settings/exceptions,
model manager, language detection, chunked transcription (fake engine),
transcript storage, transcription worker and service**. Run on every push /
PR via `.github/workflows/tests.yml`.

## Roadmap

| Phase | Scope                                                        |
| ----- | ------------------------------------------------------------ |
| 1     | Application foundation *(tagged `v0.1.0-phase1`)*            |
| 2     | Video processing engine *(tagged `v0.2.0-phase2`)*           |
| 3     | AI speech recognition engine *(current, tag next)*           |
| 4     | Subtitle generation (SRT/ASS), karaoke, rendering, export    |

## License

MIT — see the About page.
