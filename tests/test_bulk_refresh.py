"""Bulk Refresh from source: visible-row queue, confirm, cancel, module probe."""

from __future__ import annotations

from pathlib import Path

import pytest

from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.services.settings_service import Settings, SettingsStore
from taskmanager.services.task_service import CreateTaskRequest, TaskService
from taskmanager.ui.dialogs import (
    BulkRefreshConfirmDialog,
    source_refresh_confirm_phrases,
)
from taskmanager.ui.main_window import MainWindow


pytest.importorskip("PySide6")


class _FakeHost:
    def __init__(self) -> None:
        self.refresh_ids: list[int] = []
        self.download_ids: list[int] = []
        self.fail_refresh: set[int] = set()
        self.fail_download: set[int] = set()
        self.dead_modules: set[str] = set()
        self.catalogs_refreshed: list[list[str]] = []
        self._enabled = True
        self.on_refresh = None

    def enabled_modules(self):
        return ["fake"] if self._enabled else []

    def refresh_task_from_source(self, task_id: int):
        if self.on_refresh is not None:
            self.on_refresh(task_id)
        if task_id in self.fail_refresh:
            raise RuntimeError("item down")
        self.refresh_ids.append(task_id)

    def download_task_files(self, task_id: int, *, create_folder_if_missing: bool = True):
        if task_id in self.fail_download:
            raise RuntimeError("download down")
        self.download_ids.append(task_id)
        return []

    def refresh_catalogs(self, module_ids: list[str] | None = None) -> None:
        self.catalogs_refreshed.append(list(module_ids or []))

    def catalog_error(self, module_id: str) -> str | None:
        if module_id in self.dead_modules:
            return "catalog down"
        return None


def _sourced_task(service, project_id, number, *, module="fake", hidden=False):
    return service.create_task(
        CreateTaskRequest(
            project_id=project_id,
            number=number,
            create_folder=False,
            hidden=hidden,
            source_module_id=module,
            external_id=number,
            source_label=module,
        )
    )


@pytest.fixture
def bulk_env(tmp_path: Path, qtbot):
    work = tmp_path / "work"
    work.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    settings = Settings(work_dir=str(work))
    store.save(settings)
    repo = SqliteRepository(tmp_path / "bulk.db")
    service = TaskService(repo, settings)
    host = _FakeHost()
    window = MainWindow(service, settings, store, source_host=host)
    qtbot.addWidget(window)
    yield window, service, host
    repo.close()


def _accept_confirm(monkeypatch, *, download: bool = True, accepted: bool = True):
    def fake_exec(self):
        self.download_cb.setChecked(download)
        if accepted:
            return BulkRefreshConfirmDialog.DialogCode.Accepted
        return BulkRefreshConfirmDialog.DialogCode.Rejected

    monkeypatch.setattr(BulkRefreshConfirmDialog, "exec", fake_exec)


def _capture_info(monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    texts: list[str] = []

    def capture(parent, title, text, *a, **k):
        texts.append(str(text))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "information", capture)
    return texts


def test_source_refresh_confirm_phrases_both_flags():
    fields, note = source_refresh_confirm_phrases(keep_priority=False)
    assert fields == "описание, приоритет и служебные ссылки"
    assert note == "Комментарий не изменится."
    fields, note = source_refresh_confirm_phrases(keep_priority=True)
    assert fields == "описание и служебные ссылки"
    assert note == "Комментарий и приоритет не изменятся."


def test_confirm_dialog_count_and_download_checked_by_default(qtbot):
    from PySide6.QtWidgets import QLabel

    dialog = BulkRefreshConfirmDialog(4)
    qtbot.addWidget(dialog)
    dialog.show()
    labels = [w.text() for w in dialog.findChildren(QLabel)]
    assert any("4 заявок" in text for text in labels)
    assert any("Описание, приоритет и служебные ссылки перезапишутся" in text for text in labels)
    assert any("Комментарий не изменится" in text for text in labels)
    assert dialog.download_cb.isChecked()
    assert dialog.download_cb.text() == "Скачать файлы источника"


def test_confirm_dialog_keep_priority_copy(qtbot):
    from PySide6.QtWidgets import QLabel

    dialog = BulkRefreshConfirmDialog(2, keep_priority=True)
    qtbot.addWidget(dialog)
    dialog.show()
    labels = [w.text() for w in dialog.findChildren(QLabel)]
    joined = " ".join(labels)
    assert "Описание и служебные ссылки перезапишутся" in joined
    assert "Комментарий и приоритет не изменятся" in joined
    assert "приоритет и служебные" not in joined.lower()


def test_refresh_all_disabled_in_archive_and_without_source(bulk_env):
    window, service, _host = bulk_env
    project = service.create_project("P")
    _sourced_task(service, project.id, "1")
    service.create_task(
        CreateTaskRequest(project_id=project.id, number="local", create_folder=False)
    )
    window.reload_projects()
    assert window.act_refresh_all_source.isEnabled()
    window.archive_cb.setChecked(True)
    assert not window.act_refresh_all_source.isEnabled()
    window.archive_cb.setChecked(False)
    window.search_edit.setText("local")
    assert not window.act_refresh_all_source.isEnabled()


def test_queue_is_visible_sourced_rows_search_hidden_and_current_tab(
    bulk_env, monkeypatch
):
    window, service, host = bulk_env
    first = service.create_project("First")
    second = service.create_project("Second")
    t_keep = _sourced_task(service, first.id, "10")
    _sourced_task(service, first.id, "20")
    _sourced_task(service, first.id, "30", hidden=True)
    _sourced_task(service, second.id, "10")
    local = service.create_task(
        CreateTaskRequest(project_id=first.id, number="11", create_folder=False)
    )
    window.reload_projects()
    for i in range(window.tabs.count()):
        if window.tabs.tabBar().tabData(i) == first.id:
            window.tabs.setCurrentIndex(i)
            break
    window.search_edit.setText("10")
    _accept_confirm(monkeypatch, download=False)
    texts = _capture_info(monkeypatch)
    window.refresh_all_from_source()
    assert host.refresh_ids == [t_keep.id]
    assert local.id not in host.refresh_ids
    assert host.download_ids == []
    assert texts
    assert "Обновлено: 1" in texts[-1]

    host.refresh_ids.clear()
    window.search_edit.clear()
    window.hidden_cb.setChecked(True)
    window.refresh_all_from_source()
    hidden = [
        t
        for t in service.list_tasks(first.id, only_hidden=True)
        if t.has_source
    ]
    assert set(host.refresh_ids) == {t.id for t in hidden}


def test_checkbox_controls_download(bulk_env, monkeypatch):
    window, service, host = bulk_env
    project = service.create_project("P")
    task = _sourced_task(service, project.id, "1")
    window.reload_projects()
    _accept_confirm(monkeypatch, download=False)
    _capture_info(monkeypatch)
    window.refresh_all_from_source()
    assert host.refresh_ids == [task.id]
    assert host.download_ids == []

    host.refresh_ids.clear()
    _accept_confirm(monkeypatch, download=True)
    window.refresh_all_from_source()
    assert host.refresh_ids == [task.id]
    assert host.download_ids == [task.id]


def test_confirm_cancel_does_not_start(bulk_env, monkeypatch):
    window, service, host = bulk_env
    project = service.create_project("P")
    _sourced_task(service, project.id, "1")
    window.reload_projects()
    _accept_confirm(monkeypatch, accepted=False)
    window.refresh_all_from_source()
    assert host.refresh_ids == []
    assert window._bulk_refresh_panel.isHidden()


def test_cancel_between_tasks_finishes_current(bulk_env, monkeypatch):
    window, service, host = bulk_env
    project = service.create_project("P")
    first = _sourced_task(service, project.id, "1")
    second = _sourced_task(service, project.id, "2")
    window.reload_projects()

    def on_refresh(_task_id: int) -> None:
        assert not window.act_refresh_all_source.isEnabled()
        assert not window.act_import_source.isEnabled()
        assert not window._bulk_refresh_panel.isHidden()
        window._bulk_refresh_cancel_btn.click()

    host.on_refresh = on_refresh
    _accept_confirm(monkeypatch, download=True)
    texts = _capture_info(monkeypatch)
    window.refresh_all_from_source()
    assert host.refresh_ids == [first.id]
    assert host.download_ids == [first.id]
    assert second.id not in host.refresh_ids
    assert "Отменено" in texts[-1]
    assert window._bulk_refresh_panel.isHidden()
    assert window.act_refresh_all_source.isEnabled()
    assert window.act_import_source.isEnabled()


def test_item_error_continues_dead_module_skips_rest(bulk_env, monkeypatch):
    window, service, host = bulk_env
    project = service.create_project("P")
    a1 = _sourced_task(service, project.id, "A1", module="mod_a")
    a2 = _sourced_task(service, project.id, "A2", module="mod_a")
    b1 = _sourced_task(service, project.id, "B1", module="mod_b")
    window.reload_projects()

    host.fail_refresh.add(a1.id)
    _accept_confirm(monkeypatch, download=False)
    texts = _capture_info(monkeypatch)
    window.refresh_all_from_source()
    assert a1.id not in host.refresh_ids
    assert a2.id in host.refresh_ids
    assert b1.id in host.refresh_ids
    assert host.catalogs_refreshed == [["mod_a"]]
    assert "A1:" in texts[-1]
    assert "каталог" not in texts[-1]

    host.refresh_ids.clear()
    host.catalogs_refreshed.clear()
    host.dead_modules.add("mod_a")
    window.refresh_all_from_source()
    assert a1.id not in host.refresh_ids
    assert a2.id not in host.refresh_ids
    assert b1.id in host.refresh_ids
    assert ["mod_a"] in host.catalogs_refreshed
    summary = texts[-1]
    assert "каталог недоступен" in summary
    assert "Обновлено: 1" in summary


def test_no_source_host_message(bulk_env, monkeypatch):
    window, service, _host = bulk_env
    project = service.create_project("P")
    _sourced_task(service, project.id, "1")
    window.reload_projects()
    window.source_host = None
    assert window.act_refresh_all_source.isEnabled()
    texts = _capture_info(monkeypatch)
    window.refresh_all_from_source()
    assert texts[-1] == "Модули источников недоступны"


def test_progress_bar_separate_from_app_update(bulk_env):
    window, service, _host = bulk_env
    project = service.create_project("P")
    _sourced_task(service, project.id, "1")
    window.reload_projects()
    assert window.act_refresh_all_source.text() == "Обновить все…"
    assert window._bulk_refresh_panel is not window._update_panel
    assert window._bulk_refresh_panel.isHidden()
    assert window._bulk_refresh_cancel_btn.text() == "Отмена"
    assert window._update_panel.isHidden()
