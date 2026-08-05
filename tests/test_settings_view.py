"""Settings page: preferences persist to config/settings.json."""

from src.core.config_manager import ConfigManager


def test_save_button_persists_preferences(qapp, config, app_state, theme_service):
    from src.views.settings import SettingsView

    view = SettingsView(app_state, theme_service, config)

    theme_index = view.theme_combo.findData("light")
    view.theme_combo.setCurrentIndex(theme_index)
    view.language_combo.setCurrentText("Español")
    view.gpu_check.setChecked(False)
    view.output_edit.setText("C:/my_output")
    view.autosave_check.setChecked(False)
    view.channel_combo.setCurrentText("Beta")

    view._save()

    reloaded = ConfigManager(path=config.path)
    assert reloaded.get("theme") == "light"
    assert reloaded.get("language") == "Español"
    assert reloaded.get("gpu") is False
    assert reloaded.get("output_folder") == "C:/my_output"
    assert reloaded.get("autosave") is False
    assert reloaded.get("update_channel") == "beta"


def test_reset_restores_defaults_in_ui(qapp, config, app_state, theme_service):
    from src.views.settings import SettingsView

    view = SettingsView(app_state, theme_service, config)
    view.theme_combo.setCurrentIndex(view.theme_combo.findData("light"))
    view.gpu_check.setChecked(False)
    view._save()

    view._reset()
    assert config.get("theme") == "dark"
    assert config.get("gpu") is True
    assert view.theme_combo.currentData() == "dark"


def test_theme_change_flows_through_app_state(qapp, config, app_state, theme_service):
    from src.views.settings import SettingsView

    view = SettingsView(app_state, theme_service, config)
    view.theme_combo.setCurrentIndex(view.theme_combo.findData("light"))
    assert app_state.theme() == "light"
