from pathlib import Path

from taskmanager.services.settings_service import Settings, SettingsStore


def test_settings_roundtrip(tmp_path: Path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = Settings(work_dir=str(tmp_path / "work"), template_name=".tpl")
    store.save(settings)
    loaded = store.load()
    assert loaded.work_dir == settings.work_dir
    assert loaded.template_name == ".tpl"
    assert loaded.archive_name == ".archive"
    assert "Белый" in loaded.colors


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
