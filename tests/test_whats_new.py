"""«Что нового» window, settings button, and first-launch gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.services.settings_service import Settings, SettingsStore
from taskmanager.services.task_service import TaskService
from taskmanager.ui.main_window import MainWindow
from taskmanager.ui.whats_new_dialog import WhatsNewDialog, show_whats_new

pytest.importorskip("PySide6")


@pytest.fixture
def app_env(tmp_path: Path, qtbot):
    work = tmp_path / "work"
    work.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    settings = Settings(work_dir=str(work))
    store.save(settings)
    repo = SqliteRepository(tmp_path / "ui.db")
    service = TaskService(repo, settings)
    window = MainWindow(service, settings, store)
    qtbot.addWidget(window)
    yield window, service
    repo.close()

_NOTES = """
## 0.10.1

- старая линейка

## 0.11.0

- база

## 0.11.3

- патч
"""


def test_dialog_shows_current_minor_line_and_switches(qtbot):
    dialog = WhatsNewDialog(_NOTES, current_version="0.11.2")
    qtbot.addWidget(dialog)
    assert dialog.notes.isReadOnly()
    assert [dialog.version_combo.itemText(i) for i in range(dialog.version_combo.count())] == [
        "0.11",
        "0.10",
    ]
    assert dialog.version_combo.currentText() == "0.11"
    plain = dialog.notes.toPlainText()
    assert plain.index("0.11.3") < plain.index("0.11.0")
    assert "старая линейка" not in plain
    dialog.version_combo.setCurrentIndex(1)
    switched = dialog.notes.toPlainText()
    assert "старая линейка" in switched
    assert "0.11.3" not in switched


def test_dialog_without_notes_has_no_version_list(qtbot):
    dialog = WhatsNewDialog("", current_version="0.11.0")
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.version_combo.count() == 0
    assert not dialog._version_row.isVisible()
    assert dialog.notes.toPlainText() == "Заметок пока нет."


def test_auto_show_records_seen_version_once(tmp_path: Path, qtbot, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    settings = Settings(work_dir=str(work), last_seen_version="")
    store.save(settings)
    monkeypatch.setattr(WhatsNewDialog, "exec", lambda self: 0)
    assert (
        show_whats_new(
            None,
            settings,
            store,
            current_version="0.11.3",
            notes_text=_NOTES,
        )
        is True
    )
    assert settings.last_seen_version == "0.11.3"
    assert store.load().last_seen_version == "0.11.3"

    def fail_exec(self):
        raise AssertionError("window opened again")

    monkeypatch.setattr(WhatsNewDialog, "exec", fail_exec)
    assert (
        show_whats_new(
            None,
            settings,
            store,
            current_version="0.11.3",
            notes_text=_NOTES,
        )
        is False
    )


def test_missing_minor_line_does_not_open_or_record(tmp_path: Path, qtbot, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    settings = Settings(work_dir=str(work))
    store.save(settings)

    def fail_exec(self):
        raise AssertionError("window opened")

    monkeypatch.setattr(WhatsNewDialog, "exec", fail_exec)
    assert (
        show_whats_new(
            None,
            settings,
            store,
            current_version="0.12.0",
            notes_text=_NOTES,
        )
        is False
    )
    assert settings.last_seen_version == ""
    assert store.load().last_seen_version == ""


def test_settings_button_opens_whats_new_main_toolbar_does_not(app_env, qtbot, monkeypatch):
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QPushButton

    from taskmanager.ui.settings_dialog import SettingsDialog

    window, _service = app_env
    action_texts = [action.text() for action in window.findChildren(QAction)]
    assert "Что нового" not in action_texts

    calls: list[bool] = []

    def fake(parent, settings, store, *, force=False, **kwargs):
        calls.append(force)
        return True

    monkeypatch.setattr("taskmanager.ui.whats_new_dialog.show_whats_new", fake)
    dialog = SettingsDialog(window.settings, window.settings_store, window)
    qtbot.addWidget(dialog)
    button = next(
        widget
        for widget in dialog.findChildren(QPushButton)
        if widget.text() == "Что нового"
    )
    button.click()
    assert calls == [True]


def test_startup_offers_whats_new_before_update_checks(app_env, monkeypatch):
    window, _service = app_env
    window.settings.check_updates_on_startup = False
    window.settings.check_module_updates_on_startup = False
    calls: list[bool] = []

    def fake(parent, settings, store, *, force=False, **kwargs):
        assert parent is window
        assert settings is window.settings
        assert store is window.settings_store
        calls.append(force)
        return False

    monkeypatch.setattr("taskmanager.ui.whats_new_dialog.show_whats_new", fake)
    window.run_startup_update_checks()
    assert calls == [False]
