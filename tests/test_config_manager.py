"""ConfigManager: first-run defaults, persistence and recovery."""

from src.core.config_manager import ConfigManager


def test_creates_defaults_on_first_run(tmp_path):
    path = tmp_path / "settings.json"
    manager = ConfigManager(path=path)

    assert path.exists()
    assert manager.get("theme") == "dark"
    assert manager.get("output_folder") == "output"
    assert manager.get("gpu") is True


def test_set_save_and_reload(tmp_path):
    path = tmp_path / "settings.json"
    manager = ConfigManager(path=path)
    manager.set("theme", "light")
    manager.set("gpu", False)
    manager.save()

    reloaded = ConfigManager(path=path)
    assert reloaded.get("theme") == "light"
    assert reloaded.get("gpu") is False


def test_get_with_default_fallback(tmp_path):
    manager = ConfigManager(path=tmp_path / "settings.json")
    assert manager.get("does_not_exist", "fallback") == "fallback"


def test_missing_keys_are_filled_from_defaults(tmp_path):
    """An older settings file missing new keys must not break loading."""
    path = tmp_path / "settings.json"
    path.write_text('{"theme": "light"}', encoding="utf-8")

    manager = ConfigManager(path=path)
    assert manager.get("theme") == "light"
    assert manager.get("autosave") is True  # filled from defaults


def test_corrupt_file_recovers_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ this is not valid json", encoding="utf-8")

    manager = ConfigManager(path=path)
    assert manager.get("theme") == "dark"
    assert path.with_suffix(".json.bak").exists()


def test_reset_restores_defaults(tmp_path):
    path = tmp_path / "settings.json"
    manager = ConfigManager(path=path)
    manager.set("theme", "light")
    manager.save()

    manager.reset()
    assert manager.get("theme") == "dark"
