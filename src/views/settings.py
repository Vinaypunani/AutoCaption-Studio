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
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core.app_state import AppState
from ..core.config_manager import ConfigManager
from ..core.logger import get_logger
from ..services.theme_service import ThemeService
from ..widgets.cards import make_card, make_field

log = get_logger("settings_view")

_LANGUAGES = ["English", "Español", "Français", "Deutsch", "日本語"]
_CHANNELS = ["stable", "beta", "nightly"]


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

    def _on_theme_preview(self, index: int) -> None:
        theme = self.theme_combo.itemData(index)
        if theme:
            self.app_state.set_theme(theme, persist=False)  # applied now, saved on Save

    # -- actions -----------------------------------------------------------
    def _save(self) -> None:
        theme = self.theme_combo.currentData() or "dark"
        self.config.set("theme", theme)
        self.config.set("language", self.language_combo.currentText())
        self.config.set("gpu", self.gpu_check.isChecked())
        self.config.set("output_folder", self.output_edit.text().strip() or "output")
        self.config.set("autosave", self.autosave_check.isChecked())
        self.config.set("update_channel", self.channel_combo.currentText().lower())
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
