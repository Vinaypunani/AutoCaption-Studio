# 🎬 AutoCaption Studio

A modern, production-ready **PySide6** desktop application for AI-generated
video captions.

- **Phase 1 — Application Foundation** (tag `v0.1.0-phase1`): polished
  dark/light shell, navigation, settings persistence, logging, job queue.
- **Phase 2 — Video Processing Engine** (tag `v0.2.0-phase2`): real video
  validation, metadata, thumbnails, audio extraction and preview through a
  centralized FFmpeg wrapper.
- **Phase 3 — AI Speech Recognition** (tag `v0.3.0-phase3`): Whisper
  transcription with word-level timestamps, model management, hardware
  detection and results storage.
- **Phase 4 — Professional Subtitle Engine** *(current)*: SRT/ASS/VTT/JSON/TXT
  export, smart line breaking, timing optimization, punctuation cleanup,
  validation and live preview.
- **Phase 5+**: caption themes, karaoke, rendering (burned-in captions).

**Burned-in video rendering does not exist yet** — that's the rendering
phase, wired into the pipeline's `Render Ready` stage.

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
│   ├── transcripts/            # per-video JSON + TXT transcripts
│   └── subtitles/              # ★ SRT / ASS / VTT / JSON / TXT exports
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
│   │   └── pipeline.py         # job pipeline: ordered stages + runners
│   ├── models/                 # job_model (Job, stages, sample data)
│   ├── video/                  # Phase 2 engine (see below)
│   ├── ai/whisper/             # Phase 3 engine (see below)
│   ├── subtitles/              # ★ Phase 4 engine (see below)
│   ├── services/               # theme_service, video_service (pipeline),
│   │                           # transcription_service (AI stage),
│   │                           # subtitle_service (subtitle stages)
│   ├── widgets/                # sidebar, topbar, drop_zone, progress, queue,
│   │                           # video_info, cards
│   ├── views/                  # home, queue, settings, export, about
│   └── main_window.py          # composition root + frameless window
├── scripts/
│   ├── generate_logo.py
│   └── smoke_run.py            # headless end-to-end verification
├── .github/workflows/tests.yml # CI: full suite on push/PR
└── tests/                      # 321 tests (offscreen Qt + real FFmpeg)
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

### Subtitle engine (`src/subtitles/`)

| Module                | Responsibility                                       |
| --------------------- | ---------------------------------------------------- |
| `subtitle_engine.py`  | Build pipeline + pluggable `SubtitleWriter` registry |
| `srt/ass/vtt/json/txt_writer.py` | Format plugins (add TTML/SCC via `register_writer`) |
| `line_breaker.py`     | Max chars/lines, phrases, punctuation/conjunction breaks |
| `timing_optimizer.py` | Merge short, split long, gaps, overlaps, reading-speed stretch |
| `punctuation.py`      | Capitalize, whitespace, punctuation restore, contractions, fillers |
| `validator.py`        | Overlaps, negative durations, empty text, reading speed; auto-fix |
| `preview_generator.py`| Pure-HTML caption preview (what the renderer will show) |
| `subtitle_service.py` | Pipeline stages (`Subtitle Ready` → `Subtitle Validated`) + export |
| `settings.py`         | `SubtitleSettings` persisted under `subtitles`       |
| `exceptions.py`       | Typed errors: unsupported format, empty subtitles…   |

## Features

### Phase 4 — Professional Subtitle Engine
- **Multi-format export** — SRT, ASS, VTT, normalized JSON and TXT via a
  plugin `SubtitleWriter` interface; adding TTML/SCC is one `register_writer`
  call. Exports to `output/subtitles/` automatically and to any folder from
  the Export page.
- **Smart line breaking** — max chars/line, max lines/cue, phrase units kept
  together, preferred breaks after punctuation and before conjunctions,
  long-word overflow handling, and per-cue time distributed proportionally.
- **Timing optimization** — merge very short cues, split very long ones,
  minimum display durations, gap insertion, overlap correction and
  reading-speed stretching into the following gap.
- **Punctuation & cleanup** — capitalize sentences, normalize whitespace,
  restore missing punctuation, optional contraction expansion and filler-word
  removal (all toggleable).
- **Validation** — typed issues for overlaps, empty captions, excessive
  reading speed, over-long lines and too many lines, with mechanical auto-fix
  (drop empties, clamp times, fix overlaps) and lenient/balanced/strict modes.
- **Live preview** — the Queue detail panel renders captions exactly as they
  will look (dark band, centred text) with a cue list; the Export page writes
  any format for any transcribed job.
- **Pipeline integration** — `Subtitle Ready` → `Subtitle Validated` stages
  after transcription; warnings surface per job in the UI.

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
views (widgets)  →  services  →  engines (video / ai / subtitles)
      ↓                ↓                 ↓
  AppState         Pipeline         FFmpegManager / faster-whisper /
  (signals)    (core/pipeline.py)   SubtitleEngine (writer plugins)
      ↓
core (config / logging / constants)
```

- **`src/video/`** is pure Python (no Qt) except `preview.py`; everything
  spawns media processes through `FFmpegManager`.
- **`src/ai/whisper/`** isolates the ML dependency behind an engine
  protocol — tests inject a fake engine, the app uses faster-whisper.
- **`src/subtitles/`** is pure Python with a pluggable writer registry —
  formats are plugins, the engine never changes to add one.
- **`VideoService`** runs one `QThread` worker per job; stage updates flow
  back through signals to `AppState`, which notifies the views.
- **`TranscriptionService` / `SubtitleService`** register stage runners into
  the same pipeline — retries, cancellations and future stages
  (translation, speaker diarization, karaoke, rendering) hang off the same
  structure.
- Views never touch ffmpeg, files, models or subtitle writers directly.

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
    },
    "subtitles": {
        "default_format": "srt",
        "auto_generate": true,
        "max_chars_per_line": 42,
        "max_lines": 2,
        "reading_speed_cps": 21.0,
        "timing_optimization": true,
        "min_display_duration": 0.8,
        "max_display_duration": 7.0,
        "min_gap": 0.05,
        "auto_punctuation": true,
        "capitalize_sentences": true,
        "expand_contractions": false,
        "remove_fillers": false,
        "keep_phrases": true,
        "break_at_punctuation": true,
        "break_at_conjunctions": true,
        "validation_strictness": "balanced"
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

321 tests: startup, config persistence, navigation, drop-zone, models,
FFmpeg wrapper, validation, metadata, thumbnails, audio extraction, file
manager, pipeline integration (real generated videos), job pipeline (stages,
progress weights, cancellation), the full AI engine (model manager, language
detection, chunked transcription, worker, service), and the **subtitle engine
(line breaking, punctuation, timing optimization, validation, all five
writers, engine/plugin registry, preview generator, settings, pipeline
service)**. Run on every push / PR via `.github/workflows/tests.yml`.

## Roadmap

| Phase | Scope                                                        |
| ----- | ------------------------------------------------------------ |
| 1     | Application foundation *(tagged `v0.1.0-phase1`)*            |
| 2     | Video processing engine *(tagged `v0.2.0-phase2`)*           |
| 3     | AI speech recognition engine *(tagged `v0.3.0-phase3`)*      |
| 4     | Professional subtitle engine *(current, tag next)*           |
| 5     | Caption themes, karaoke animation, rendering, final export   |

## License

MIT — see the About page.
