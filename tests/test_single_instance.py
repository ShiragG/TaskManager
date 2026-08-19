from pathlib import Path

import pytest

pytest.importorskip("PySide6")


def test_second_run_raises_existing_and_skips_window(tmp_path: Path, qtbot, monkeypatch):
    from PySide6.QtWidgets import QApplication

    from taskmanager.infrastructure.single_instance import InstanceGuard
    from taskmanager.main import run
    from taskmanager.services.settings_service import Settings, SettingsStore

    work = tmp_path / "work"
    work.mkdir()
    SettingsStore(tmp_path / "settings.json").save(Settings(work_dir=str(work)))

    monkeypatch.setattr(
        "taskmanager.infrastructure.single_instance.app_dir", lambda: tmp_path
    )
    monkeypatch.setattr("taskmanager.main.default_settings_path", lambda: tmp_path / "settings.json")
    monkeypatch.setattr("taskmanager.main.default_db_path", lambda: tmp_path / "taskmanager.db")
    monkeypatch.setattr("taskmanager.infrastructure.paths.app_dir", lambda: tmp_path)

    created: list[object] = []

    class FakeWindow:
        def __init__(self, *args, **kwargs) -> None:
            created.append(self)

        def setWindowIcon(self, *_args) -> None:
            return None

        def show(self) -> None:
            return None

        def bring_to_front(self) -> None:
            return None

        def run_startup_update_checks(self) -> None:
            return None

    monkeypatch.setattr("taskmanager.main.MainWindow", FakeWindow)

    primary = InstanceGuard(tmp_path)
    assert primary.try_become_primary()
    shown: list[bool] = []
    primary.show_requested.connect(lambda: shown.append(True))

    code = run(["taskmanager"])
    assert code == 0
    assert created == []
    qtbot.waitUntil(lambda: shown == [True], timeout=2000)
    primary.release()
    assert QApplication.instance() is not None
