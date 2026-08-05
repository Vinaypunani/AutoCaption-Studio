"""Video preview player (QtMultimedia).

A small playback panel with play / pause / stop and a seek slider. When
PySide6-Addons (QtMultimedia) is not installed the panel renders a friendly
notice and disables its controls, so the app keeps working.
"""

from __future__ import annotations

from PySide6.QtCore import QUrl, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..core.logger import get_logger
from .metadata import format_duration

try:  # PySide6-Addons ships QtMultimedia; degrade gracefully without it.
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget

    QTMULTIMEDIA_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on install
    QAudioOutput = None  # type: ignore
    QMediaPlayer = None  # type: ignore
    QVideoWidget = None  # type: ignore
    QTMULTIMEDIA_AVAILABLE = False

log = get_logger("preview")


class PreviewPanel(QFrame):
    """Play / pause / stop / seek controls plus the video surface."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PreviewPanel")
        self._source_path = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._video_widget = None
        if QTMULTIMEDIA_AVAILABLE:
            self._player = QMediaPlayer(self)
            self._audio = QAudioOutput(self)
            self._audio.setVolume(0.8)
            self._player.setAudioOutput(self._audio)
            self._video_widget = QVideoWidget()
            self._video_widget.setObjectName("PreviewSurface")
            self._video_widget.setMinimumHeight(180)
            self._player.setVideoOutput(self._video_widget)
            layout.addWidget(self._video_widget, 1)
        else:
            notice = QLabel(
                "🎬 Video preview requires PySide6-Addons (QtMultimedia).\n"
                "Install it (see README) to play videos inside the app."
            )
            notice.setObjectName("EmptyState")
            notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
            notice.setMinimumHeight(180)
            layout.addWidget(notice, 1)

        # -- controls -------------------------------------------------------
        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.play_button = QPushButton("▶")
        self.play_button.setObjectName("GhostButton")
        self.play_button.setFixedWidth(56)
        self.play_button.setToolTip("Play")
        self.play_button.clicked.connect(self.toggle_playback)

        self.stop_button = QPushButton("⏹")
        self.stop_button.setObjectName("GhostButton")
        self.stop_button.setFixedWidth(56)
        self.stop_button.setToolTip("Stop")
        self.stop_button.clicked.connect(self.stop)

        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.setEnabled(False)
        self.position_slider.setToolTip("Seek")
        self.position_slider.sliderMoved.connect(self._seek_to)

        self.time_label = QLabel("00:00 / —")
        self.time_label.setObjectName("JobEta")
        self.time_label.setMinimumWidth(110)

        controls.addWidget(self.play_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.position_slider, 1)
        controls.addWidget(self.time_label)
        layout.addLayout(controls)

        self._controls_enabled = QTMULTIMEDIA_AVAILABLE
        self._set_controls_enabled(False)

        if QTMULTIMEDIA_AVAILABLE:
            self._player.positionChanged.connect(self._on_position_changed)
            self._player.durationChanged.connect(self._on_duration_changed)
            self._player.playbackStateChanged.connect(self._on_state_changed)
            self._player.errorOccurred.connect(self._on_error)

    # -- public API ---------------------------------------------------------
    def set_source(self, video_path: str) -> None:
        """Load a video file for playback (path must exist)."""
        self._source_path = video_path
        if not QTMULTIMEDIA_AVAILABLE:
            return
        self._player.stop()
        self._player.setSource(QUrl.fromLocalFile(video_path))
        self.position_slider.setRange(0, 0)
        self.position_slider.setEnabled(True)
        self.time_label.setText("00:00 / —")
        self._set_controls_enabled(True)

    def clear(self) -> None:
        """Unload the current source and disable controls."""
        if QTMULTIMEDIA_AVAILABLE:
            self._player.stop()
            self._player.setSource(QUrl())
        self._source_path = ""
        self.position_slider.setRange(0, 0)
        self.position_slider.setEnabled(False)
        self.time_label.setText("00:00 / —")
        self._set_controls_enabled(False)

    def has_source(self) -> bool:
        return bool(self._source_path)

    def is_playing(self) -> bool:
        if not QTMULTIMEDIA_AVAILABLE:
            return False
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    # -- actions -------------------------------------------------------------
    def toggle_playback(self) -> None:
        if not QTMULTIMEDIA_AVAILABLE or not self._source_path:
            return
        if self.is_playing():
            self._player.pause()
        else:
            self._player.play()

    def stop(self) -> None:
        if QTMULTIMEDIA_AVAILABLE:
            self._player.stop()

    # -- player wiring -------------------------------------------------------
    def _seek_to(self, position_ms: int) -> None:
        if QTMULTIMEDIA_AVAILABLE:
            self._player.setPosition(position_ms)

    def _on_position_changed(self, position_ms: int) -> None:
        if not self.position_slider.isSliderDown():
            self.position_slider.setValue(position_ms)
        self.time_label.setText(f"{format_duration(position_ms / 1000)} / {format_duration(self._player.duration() / 1000)}")

    def _on_duration_changed(self, duration_ms: int) -> None:
        self.position_slider.setRange(0, max(0, duration_ms))
        self.time_label.setText(f"{format_duration(self._player.position() / 1000)} / {format_duration(duration_ms / 1000)}")

    def _on_state_changed(self, state) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_button.setText("⏸" if playing else "▶")

    def _on_error(self, error, error_string: str) -> None:
        log.warning("Preview playback error %s: %s", error, error_string)

    # -- helpers ---------------------------------------------------------------
    def _set_controls_enabled(self, enabled: bool) -> None:
        self.play_button.setEnabled(enabled)
        self.stop_button.setEnabled(enabled)
        self.position_slider.setEnabled(enabled and QTMULTIMEDIA_AVAILABLE)
