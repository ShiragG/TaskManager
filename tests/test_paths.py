import sys
from pathlib import Path

from taskmanager.infrastructure.paths import (
    app_dir,
    default_db_path,
    default_settings_path,
)


def test_app_dir_dev_uses_cwd(monkeypatch, tmp_path: Path):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.chdir(tmp_path)
    assert app_dir() == tmp_path.resolve()
    assert default_settings_path() == tmp_path.resolve() / "settings.json"
    assert default_db_path() == tmp_path.resolve() / "taskmanager.db"


def test_app_dir_frozen_uses_executable_parent(monkeypatch, tmp_path: Path):
    exe = tmp_path / "bin" / "TaskManager"
    exe.parent.mkdir()
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    assert app_dir() == exe.parent.resolve()
    assert default_db_path().name == "taskmanager.db"
    assert default_settings_path().parent == exe.parent.resolve()
