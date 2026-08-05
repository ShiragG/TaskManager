from pathlib import Path

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
