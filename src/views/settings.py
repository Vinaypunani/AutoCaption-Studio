"""Settings page.

Persists preferences to ``config/settings.json`` through the ConfigManager.
No settings are written until "Save Settings" is pressed (the theme combo
live-previews, but is only persisted on save).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..ai.whisper.model_manager import MODEL_CATALOG, detect_device
from ..ai.whisper.settings import COMMON_LANGUAGES, ComputeType, DeviceType, LanguageMode, WhisperSettings
from ..core.app_state import AppState
from ..core.config_manager import ConfigManager
from ..core.constants import SUBTITLE_FORMATS
from ..core.logger import get_logger
from ..services.theme_service import ThemeService
from ..subtitles.settings import SubtitleSettings
from ..widgets.cards import make_card, make_field

log = get_logger("settings_view")

_LANGUAGES = ["English", "Español", "Français", "Deutsch", "日本語"]
_CHANNELS = ["stable", "beta", "nightly"]

_DEVICE_LABELS = {
    "auto": f"Auto ({detect_device()})",
    "cpu": "CPU",
    "cuda": "NVIDIA CUDA",
    "directml": "DirectML (future)",
    "metal": "Apple Metal (future)",
}
_COMPUTE_LABELS = {
    "default": "Default (int8 on CPU / float16 on GPU)",
    "int8": "int8 (fast, lower quality)",
    "float16": "float16 (GPU)",
    "float32": "float32 (highest quality)",
}


def _mb(size_hint_gb: float) -> str:
    return f"~{int(size_hint_gb * 1024)} MB"


class SettingsView(QWidget):
    """Application settings page."""

    def __init__(
        self,
        app_state: AppState,
        theme_service: ThemeService,
        config: ConfigManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_state = app_state
        self.theme_service = theme_service
        self.config = config
        self.setObjectName("SettingsView")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        outer = QVBoxLayout(body)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        outer.addWidget(title)

        subtitle = QLabel("Preferences are saved to config/settings.json")
        subtitle.setObjectName("PageSubtitle")
        outer.addWidget(subtitle)

        # -- appearance ------------------------------------------------------
        appearance = QWidget()
        form = QVBoxLayout(appearance)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName("SettingsCombo")
        for theme in self.theme_service.available_themes():
            self.theme_combo.addItem(self.theme_service.display_name(theme), theme)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_preview)
        form.addWidget(make_field("Theme", self.theme_combo))

        self.language_combo = QComboBox()
        self.language_combo.setObjectName("SettingsCombo")
        self.language_combo.addItems(_LANGUAGES)
        self.language_combo.setToolTip("UI language — localization arrives in a later phase")
        form.addWidget(make_field("Language", self.language_combo))
        outer.addWidget(make_card("Appearance", appearance))

        # -- processing ------------------------------------------------------
        processing = QWidget()
        p_form = QVBoxLayout(processing)
        p_form.setContentsMargins(0, 0, 0, 0)
        p_form.setSpacing(10)

        self.gpu_check = QCheckBox("Use GPU acceleration when available")
        self.gpu_check.setToolTip("Reserved for later phases — no GPU work happens in Phase 1")
        p_form.addWidget(self.gpu_check)

        note = QLabel("GPU acceleration is reserved for later captioning phases.")
        note.setObjectName("HintText")
        note.setWordWrap(True)
        p_form.addWidget(note)
        outer.addWidget(make_card("Processing", processing))

        # -- output -----------------------------------------------------------
        output = QWidget()
        o_form = QVBoxLayout(output)
        o_form.setContentsMargins(0, 0, 0, 0)
        o_form.setSpacing(10)

        folder_widget = QWidget()
        folder_row = QHBoxLayout(folder_widget)
        folder_row.setContentsMargins(0, 0, 0, 0)
        folder_row.setSpacing(8)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("output")
        self.output_edit.setToolTip("Default folder for exported files (later phases)")
        folder_row.addWidget(self.output_edit, 1)
        browse = QPushButton("Browse…")
        browse.setObjectName("GhostButton")
        browse.setCursor(Qt.CursorShape.PointingHandCursor)
        browse.clicked.connect(self._browse_output)
        folder_row.addWidget(browse)
        o_form.addWidget(make_field("Default Output Folder", folder_widget))

        self.autosave_check = QCheckBox("Autosave projects automatically")
        self.autosave_check.setToolTip("Reserved for later phases")
        o_form.addWidget(self.autosave_check)
        outer.addWidget(make_card("Output", output))

        # -- AI / transcription ---------------------------------------------------
        ai_widget = QWidget()
        ai_form = QVBoxLayout(ai_widget)
        ai_form.setContentsMargins(0, 0, 0, 0)
        ai_form.setSpacing(10)

        self.model_combo = QComboBox()
        self.model_combo.setObjectName("SettingsCombo")
        for name, meta in MODEL_CATALOG.items():
            self.model_combo.addItem(f"{name} ({_mb(meta['size_hint_gb'])})", name)
        ai_form.addWidget(make_field("Active Model (downloads on first use)", self.model_combo))

        self.device_combo = QComboBox()
        self.device_combo.setObjectName("SettingsCombo")
        for key, label in _DEVICE_LABELS.items():
            self.device_combo.addItem(label, key)
        ai_form.addWidget(make_field("Device", self.device_combo))

        self.compute_combo = QComboBox()
        self.compute_combo.setObjectName("SettingsCombo")
        for key, label in _COMPUTE_LABELS.items():
            self.compute_combo.addItem(label, key)
        ai_form.addWidget(make_field("Compute Type", self.compute_combo))

        beam_row = QHBoxLayout()
        beam_row.setSpacing(12)
        self.beam_spin = QSpinBox()
        self.beam_spin.setRange(1, 20)
        self.beam_spin.setValue(5)
        beam_row.addWidget(make_field("Beam Size", self.beam_spin), 1)
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(0, 64)
        self.threads_spin.setValue(0)
        self.threads_spin.setToolTip("0 = let the engine decide")
        beam_row.addWidget(make_field("CPU Threads (0 = auto)", self.threads_spin), 1)
        ai_form.addLayout(beam_row)

        self.language_mode_combo = QComboBox()
        self.language_mode_combo.setObjectName("SettingsCombo")
        self.language_mode_combo.addItem("Auto-detect", "auto")
        self.language_mode_combo.addItem("Manual", "manual")
        self.language_mode_combo.currentIndexChanged.connect(self._sync_language_enabled)
        ai_form.addWidget(make_field("Language Mode", self.language_mode_combo))

        self.whisper_language_combo = QComboBox()
        self.whisper_language_combo.setObjectName("SettingsCombo")
        for code, label in COMMON_LANGUAGES.items():
            self.whisper_language_combo.addItem(f"{label} ({code})", code)
        ai_form.addWidget(make_field("Language (manual mode)", self.whisper_language_combo))

        self.auto_transcribe_check = QCheckBox("Auto-transcribe after audio extraction")
        self.auto_transcribe_check.setToolTip("Runs the Whisper stage for every processed video")
        ai_form.addWidget(self.auto_transcribe_check)
        outer.addWidget(make_card("AI / Transcription", ai_widget))

        # -- subtitles (Phase 4) --------------------------------------------------
        sub_widget = QWidget()
        sub_form = QVBoxLayout(sub_widget)
        sub_form.setContentsMargins(0, 0, 0, 0)
        sub_form.setSpacing(10)

        row1 = QHBoxLayout()
        row1.setSpacing(12)
        self.subtitle_format_combo = QComboBox()
        self.subtitle_format_combo.setObjectName("SettingsCombo")
        for fmt in SUBTITLE_FORMATS:
            self.subtitle_format_combo.addItem(fmt.upper(), fmt)
        row1.addWidget(make_field("Default Subtitle Format", self.subtitle_format_combo), 1)
        self.strictness_combo = QComboBox()
        self.strictness_combo.setObjectName("SettingsCombo")
        self.strictness_combo.addItems(["Lenient", "Balanced", "Strict"])
        row1.addWidget(make_field("Validation Strictness", self.strictness_combo), 1)
        sub_form.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(12)
        self.max_chars_spin = QSpinBox()
        self.max_chars_spin.setRange(10, 200)
        self.max_chars_spin.setValue(42)
        row2.addWidget(make_field("Max Chars / Line", self.max_chars_spin), 1)
        self.max_lines_spin = QSpinBox()
        self.max_lines_spin.setRange(1, 4)
        self.max_lines_spin.setValue(2)
        row2.addWidget(make_field("Max Lines / Cue", self.max_lines_spin), 1)
        self.reading_speed_spin = QDoubleSpinBox()
        self.reading_speed_spin.setRange(5.0, 60.0)
        self.reading_speed_spin.setValue(21.0)
        self.reading_speed_spin.setSuffix(" cps")
        row2.addWidget(make_field("Reading Speed", self.reading_speed_spin), 1)
        sub_form.addLayout(row2)

        row3 = QHBoxLayout()
        row3.setSpacing(12)
        self.min_duration_spin = QDoubleSpinBox()
        self.min_duration_spin.setRange(0.1, 5.0)
        self.min_duration_spin.setValue(0.8)
        self.min_duration_spin.setSingleStep(0.1)
        self.min_duration_spin.setSuffix(" s")
        row3.addWidget(make_field("Min Display Duration", self.min_duration_spin), 1)
        self.max_duration_spin = QDoubleSpinBox()
        self.max_duration_spin.setRange(1.0, 30.0)
        self.max_duration_spin.setValue(7.0)
        self.max_duration_spin.setSingleStep(0.5)
        self.max_duration_spin.setSuffix(" s")
        row3.addWidget(make_field("Max Display Duration", self.max_duration_spin), 1)
        sub_form.addLayout(row3)

        self.timing_optimization_check = QCheckBox("Timing optimization (merge/split/gaps)")
        self.timing_optimization_check.setToolTip("Merge very short cues, split very long ones, keep minimum gaps")
        sub_form.addWidget(self.timing_optimization_check)
        self.auto_punctuation_check = QCheckBox("Auto punctuation & capitalization")
        self.auto_punctuation_check.setToolTip("Restore missing punctuation and capitalize sentences")
        sub_form.addWidget(self.auto_punctuation_check)
        self.capitalize_check = QCheckBox("Capitalize sentences")
        sub_form.addWidget(self.capitalize_check)
        self.expand_contractions_check = QCheckBox("Expand contractions (don't → do not)")
        sub_form.addWidget(self.expand_contractions_check)
        self.remove_fillers_check = QCheckBox("Remove filler words (um, uh, er…)")
        sub_form.addWidget(self.remove_fillers_check)
        self.auto_generate_subtitles_check = QCheckBox("Auto-generate subtitles after transcription")
        self.auto_generate_subtitles_check.setToolTip("Runs the subtitle stages for every transcribed job")
        sub_form.addWidget(self.auto_generate_subtitles_check)
        outer.addWidget(make_card("Subtitles (Phase 4)", sub_widget))

        # -- updates -----------------------------------------------------------
        updates = QWidget()
        u_form = QVBoxLayout(updates)
        u_form.setContentsMargins(0, 0, 0, 0)
        u_form.setSpacing(10)

        self.channel_combo = QComboBox()
        self.channel_combo.setObjectName("SettingsCombo")
        self.channel_combo.addItems([c.title() for c in _CHANNELS])
        u_form.addWidget(make_field("Update Channel", self.channel_combo))
        outer.addWidget(make_card("Updates", updates))

        # -- actions -----------------------------------------------------------
        actions = QHBoxLayout()
        actions.setSpacing(8)
        save = QPushButton("Save Settings")
        save.setObjectName("PrimaryButton")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self._save)
        actions.addWidget(save)

        reset = QPushButton("Reset to Defaults")
        reset.setObjectName("GhostButton")
        reset.setCursor(Qt.CursorShape.PointingHandCursor)
        reset.clicked.connect(self._reset)
        actions.addWidget(reset)

        actions.addStretch(1)
        outer.addLayout(actions)
        outer.addStretch(1)

        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        self._load_values()

    # -- data binding ------------------------------------------------------
    def _load_values(self) -> None:
        theme = str(self.config.get("theme", "dark"))
        index = self.theme_combo.findData(theme)
        self.theme_combo.setCurrentIndex(max(0, index))

        language = str(self.config.get("language", "English"))
        self.language_combo.setCurrentText(language)

        self.gpu_check.setChecked(bool(self.config.get("gpu", True)))
        self.autosave_check.setChecked(bool(self.config.get("autosave", True)))
        self.output_edit.setText(str(self.config.get("output_folder", "output")))

        channel = str(self.config.get("update_channel", "stable"))
        self.channel_combo.setCurrentText(channel.title())

        subtitles = SubtitleSettings.from_config(self.config)
        index = self.subtitle_format_combo.findData(subtitles.default_format)
        self.subtitle_format_combo.setCurrentIndex(max(0, index))
        self.strictness_combo.setCurrentText(subtitles.validation_strictness.title())
        self.max_chars_spin.setValue(subtitles.max_chars_per_line)
        self.max_lines_spin.setValue(subtitles.max_lines)
        self.reading_speed_spin.setValue(subtitles.reading_speed_cps)
        self.min_duration_spin.setValue(subtitles.min_display_duration)
        self.max_duration_spin.setValue(subtitles.max_display_duration)
        self.timing_optimization_check.setChecked(subtitles.timing_optimization)
        self.auto_punctuation_check.setChecked(subtitles.auto_punctuation)
        self.capitalize_check.setChecked(subtitles.capitalize_sentences)
        self.expand_contractions_check.setChecked(subtitles.expand_contractions)
        self.remove_fillers_check.setChecked(subtitles.remove_fillers)
        self.auto_generate_subtitles_check.setChecked(subtitles.auto_generate)

        whisper = WhisperSettings.from_config(self.config)
        index = self.model_combo.findData(whisper.model)
        self.model_combo.setCurrentIndex(max(0, index))
        index = self.device_combo.findData(whisper.device.value)
        self.device_combo.setCurrentIndex(max(0, index))
        index = self.compute_combo.findData(whisper.compute_type.value)
        self.compute_combo.setCurrentIndex(max(0, index))
        self.beam_spin.setValue(whisper.beam_size)
        self.threads_spin.setValue(whisper.threads)
        mode_index = 0 if whisper.language_mode.value == "auto" else 1
        self.language_mode_combo.setCurrentIndex(mode_index)
        lang_index = self.whisper_language_combo.findData(whisper.language)
        self.whisper_language_combo.setCurrentIndex(max(0, lang_index))
        self.auto_transcribe_check.setChecked(whisper.auto_transcribe)
        self._sync_language_enabled()

    def _on_theme_preview(self, index: int) -> None:
        theme = self.theme_combo.itemData(index)
        if theme:
            self.app_state.set_theme(theme, persist=False)  # applied now, saved on Save

    # -- actions -----------------------------------------------------------
    def _sync_language_enabled(self) -> None:
        manual = self.language_mode_combo.currentData() == "manual"
        self.whisper_language_combo.setEnabled(manual)

    def _save(self) -> None:
        theme = self.theme_combo.currentData() or "dark"
        self.config.set("theme", theme)
        self.config.set("language", self.language_combo.currentText())
        self.config.set("gpu", self.gpu_check.isChecked())
        self.config.set("output_folder", self.output_edit.text().strip() or "output")
        self.config.set("autosave", self.autosave_check.isChecked())
        self.config.set("update_channel", self.channel_combo.currentText().lower())
        whisper = WhisperSettings(
            model=self.model_combo.currentData() or "tiny",
            device=DeviceType(self.device_combo.currentData() or "auto"),
            beam_size=self.beam_spin.value(),
            compute_type=ComputeType(self.compute_combo.currentData() or "default"),
            language_mode=LanguageMode(self.language_mode_combo.currentData() or "auto"),
            language=self.whisper_language_combo.currentData() or "en",
            threads=self.threads_spin.value(),
            auto_transcribe=self.auto_transcribe_check.isChecked(),
        )
        whisper.validate()
        whisper.save_to_config(self.config)

        subtitles = SubtitleSettings(
            default_format=self.subtitle_format_combo.currentData() or "srt",
            auto_generate=self.auto_generate_subtitles_check.isChecked(),
            max_chars_per_line=self.max_chars_spin.value(),
            max_lines=self.max_lines_spin.value(),
            reading_speed_cps=self.reading_speed_spin.value(),
            timing_optimization=self.timing_optimization_check.isChecked(),
            min_display_duration=self.min_duration_spin.value(),
            max_display_duration=self.max_duration_spin.value(),
            auto_punctuation=self.auto_punctuation_check.isChecked(),
            capitalize_sentences=self.capitalize_check.isChecked(),
            expand_contractions=self.expand_contractions_check.isChecked(),
            remove_fillers=self.remove_fillers_check.isChecked(),
            validation_strictness=self.strictness_combo.currentText().lower(),
        )
        subtitles.validate()
        subtitles.save_to_config(self.config)
        self.config.save()
        self.app_state.set_theme(theme, persist=False)
        self.app_state.set_status("Settings saved to config/settings.json")
        log.info("Settings saved")

    def _reset(self) -> None:
        self.config.reset()
        self._load_values()
        self.app_state.set_theme(str(self.config.get("theme", "dark")), persist=False)
        self.app_state.set_status("Settings reset to defaults")
        log.info("Settings reset to defaults")

    def _browse_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose default output folder")
        if folder:
            self.output_edit.setText(folder)
