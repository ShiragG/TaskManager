from pathlib import Path
import json

from taskmanager.services.settings_service import Settings, SettingsStore


def test_settings_roundtrip(tmp_path: Path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = Settings(
        work_dir=str(tmp_path / "work"),
        template_name=".tpl",
        warning_lead_days=3,
    )
    store.save(settings)
    loaded = store.load()
    assert loaded.work_dir == settings.work_dir
    assert loaded.template_name == ".tpl"
    assert loaded.archive_name == ".archive"
    assert loaded.warning_lead_days == 3
    assert loaded.create_notes_file is True
    assert loaded.create_task_folder is True
    assert loaded.theme_mode == "system"
    assert "Белый" in loaded.colors


def test_settings_default_lead_days(tmp_path: Path):
    work = tmp_path / "w"
    work.mkdir()
    path = tmp_path / "settings.json"
    path.write_text(
        f'{{"work_dir": "{work.as_posix()}"}}',
        encoding="utf-8",
    )
    loaded = SettingsStore(path).load()
    assert loaded.warning_lead_days == 1
    assert loaded.create_notes_file is True


def test_settings_create_notes_file_roundtrip(tmp_path: Path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = Settings(work_dir=str(tmp_path / "work"), create_notes_file=False)
    store.save(settings)
    loaded = store.load()
    assert loaded.create_notes_file is False


def test_settings_drops_legacy_source_modules(tmp_path: Path):
    work = tmp_path / "w"
    work.mkdir()
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "work_dir": str(work),
                "source_modules": [
                    {
                        "module_id": "razr",
                        "enabled": True,
                        "github_repo": "https://github.com/ShiragG/taskmanager-source-razr",
                        "display_name": "Разработка (razr)",
                        "login": "user",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    store = SettingsStore(path)
    loaded = store.load()
    assert "source_modules" not in loaded.to_dict()
    assert len(store.pending_source_module_migration) == 1
    assert store.pending_source_module_migration[0].module_id == "razr"
    assert store.pending_source_module_migration[0].enabled is True
    assert "password" not in store.pending_source_module_migration[0].to_dict()


def test_settings_hotkeys_roundtrip(tmp_path: Path):
    from taskmanager.services.hotkeys import validate_hotkeys

    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = Settings(
        work_dir=str(tmp_path / "work"),
        hotkeys={"focus_search": "Ctrl+K", "add_task": "Ctrl+N", "reload_current_tab": "F5"},
    )
    store.save(settings)
    loaded = SettingsStore(path).load()
    assert loaded.hotkeys["focus_search"] == "Ctrl+K"
    assert loaded.hotkeys["add_task"] == "Ctrl+N"
    assert (
        validate_hotkeys(
            {"focus_search": "Ctrl+N", "add_task": "Ctrl+N", "reload_current_tab": "F5"}
        )
        is not None
    )
    assert (
        validate_hotkeys(
            {"focus_search": "", "add_task": "Ctrl+N", "reload_current_tab": "F5"}
        )
        is not None
    )
    assert validate_hotkeys(loaded.hotkeys) is None


def test_settings_drops_unknown_keys(tmp_path: Path):
    work = tmp_path / "w"
    work.mkdir()
    path = tmp_path / "settings.json"
    path.write_text(
        f'{{"work_dir": "{work.as_posix()}", "dsn": "oracle", "far": "x"}}',
        encoding="utf-8",
    )
    loaded = SettingsStore(path).load()
    data = loaded.to_dict()
    assert "dsn" not in data
    assert "far" not in data
    assert data["work_dir"] == str(work) or data["work_dir"] == work.as_posix()
