"""«По номеру»: one source id opens the create card; several go bulk."""

from __future__ import annotations

from pathlib import Path

import pytest

from taskmanager.services.settings_service import Settings, SettingsStore, SourceModuleConfig
from taskmanager.services.source_host import ModuleCatalogCache, SourceHost
from taskmanager.services.source_protocol import SourceDraft, SourceModuleError
from taskmanager.services.task_service import CreateTaskRequest, TaskService
from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.ui.source_import_dialog import (
    SourceImportDialog,
    parse_source_item_ids,
)

pytest.importorskip("PySide6")


def test_parse_source_item_ids_splits_dedupes_and_keeps_order():
    assert parse_source_item_ids("  b\na  b\t a c ") == ["b", "a", "c"]
    assert parse_source_item_ids("   \n\t") == []
    assert parse_source_item_ids("42") == ["42"]


def _import_dialog(tmp_path: Path, qtbot, *, imported: list[str] | None = None):
    from PySide6.QtWidgets import QMessageBox

    work = tmp_path / "work"
    work.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    settings = Settings(work_dir=str(work))
    store.save(settings)
    repo = SqliteRepository(tmp_path / "import-numbers.db")
    service = TaskService(repo, settings)
    project = service.create_project("Nums")
    for external_id in imported or []:
        service.create_task(
            CreateTaskRequest(
                project_id=project.id,
                number=external_id,
                description="",
                create_folder=False,
                source_module_id="nums",
                external_id=external_id,
            )
        )
    fetched: list[str] = []

    class _Mod:
        id = "nums"
        display_name = "Nums"
        version = "1"
        api_version = "1"

        def configure(self, *, login, password):
            return None

        def list_statuses(self):
            return []

        def list_priorities(self):
            return []

        def list_items(self, page=1, status_filters=None):
            raise AssertionError("list not used")

        def get_item(self, external_id):
            fetched.append(external_id)
            if external_id == "bad":
                raise SourceModuleError("нет карточки")
            return SourceDraft(
                external_id=external_id,
                number=f"N-{external_id}",
                description="body",
                priority=1,
            )

        def download_files(self, *args, **kwargs):
            return []

    host = SourceHost(repo, settings, service, modules_base=tmp_path)
    host._by_id["nums"] = type(
        "L",
        (),
        {
            "config": SourceModuleConfig(
                module_id="nums", display_name="Nums", enabled=True
            ),
            "manifest": None,
            "module": _Mod(),
            "load_error": None,
        },
    )()
    host._catalogs["nums"] = ModuleCatalogCache(statuses=[], priorities=[], error=None)
    host.get_credentials = lambda mid: ("u", "p")  # type: ignore[method-assign]

    dialog = SourceImportDialog(host, project_id=project.id)
    qtbot.addWidget(dialog)
    batches: list[tuple[str, list[str]]] = []
    dialog.bulk_import_requested.connect(
        lambda module_id, ids: batches.append((module_id, list(ids)))
    )
    return dialog, fetched, batches, QMessageBox


def _unexpected_question(*args, **kwargs):
    raise AssertionError(args)


def test_one_number_opens_create_card(tmp_path: Path, qtbot, monkeypatch):
    dialog, fetched, batches, message_box = _import_dialog(tmp_path, qtbot)
    monkeypatch.setattr(message_box, "question", _unexpected_question)
    dialog.number_edit.setPlainText("7\n")
    dialog.download_cb.setChecked(False)
    dialog._fetch_by_number()
    assert fetched == ["7"]
    assert batches == []
    assert dialog.draft is not None
    assert dialog.draft.number == "N-7"
    assert dialog.module_id == "nums"
    assert dialog.download_files is False
    assert dialog.result() == dialog.DialogCode.Accepted
    dialog._host.repo.close()


def test_repeated_single_id_still_opens_create_card(tmp_path: Path, qtbot):
    dialog, fetched, batches, _message_box = _import_dialog(tmp_path, qtbot)
    dialog.number_edit.setPlainText("7 7\n7")
    dialog._fetch_by_number()
    assert fetched == ["7"]
    assert batches == []
    assert dialog.result() == dialog.DialogCode.Accepted
    dialog._host.repo.close()


def test_several_numbers_emit_bulk_without_create_card(tmp_path: Path, qtbot, monkeypatch):
    dialog, fetched, batches, message_box = _import_dialog(tmp_path, qtbot, imported=["2"])
    asked: list[str] = []

    def question(*args, **kwargs):
        asked.append(args[2])
        return message_box.StandardButton.Yes

    monkeypatch.setattr(message_box, "question", question)
    dialog.download_cb.setChecked(True)
    dialog.number_edit.setPlainText("1\n2 1\t3")
    dialog._fetch_by_number()
    assert fetched == []
    assert dialog.draft is None
    assert dialog.result() != dialog.DialogCode.Accepted
    assert batches == [("nums", ["1", "3"])]
    assert asked == [
        "Импортировать 2 элементов?\nПропущено уже импортированных: 1."
    ]
    assert dialog.download_files is True
    dialog._host.repo.close()


def test_several_numbers_decline_does_not_start(tmp_path: Path, qtbot, monkeypatch):
    dialog, fetched, batches, message_box = _import_dialog(tmp_path, qtbot)
    monkeypatch.setattr(
        message_box,
        "question",
        lambda *args, **kwargs: message_box.StandardButton.No,
    )
    dialog.number_edit.setPlainText("1 2")
    dialog._fetch_by_number()
    assert fetched == []
    assert batches == []
    assert dialog.draft is None
    assert dialog.result() != dialog.DialogCode.Accepted
    dialog._host.repo.close()


def test_one_new_id_among_imported_stays_on_bulk_path(tmp_path: Path, qtbot, monkeypatch):
    dialog, fetched, batches, message_box = _import_dialog(tmp_path, qtbot, imported=["9"])
    monkeypatch.setattr(message_box, "question", _unexpected_question)
    dialog.number_edit.setPlainText("9 4")
    dialog._fetch_by_number()
    assert fetched == []
    assert batches == [("nums", ["4"])]
    assert dialog.draft is None
    dialog._host.repo.close()


def test_all_pasted_ids_already_imported(tmp_path: Path, qtbot, monkeypatch):
    dialog, fetched, batches, message_box = _import_dialog(
        tmp_path, qtbot, imported=["2", "8"]
    )
    notes: list[str] = []

    def information(*args, **kwargs):
        notes.append(args[2])
        return message_box.StandardButton.Ok

    monkeypatch.setattr(message_box, "information", information)
    dialog.number_edit.setPlainText("2\n2")
    dialog._fetch_by_number()
    assert notes == ["Этот элемент уже импортирован в текущий проект."]
    assert fetched == []
    assert batches == []

    notes.clear()
    dialog.number_edit.setPlainText("2 8")
    dialog._fetch_by_number()
    assert notes == ["Эти элементы уже импортированы в текущий проект."]
    assert batches == []
    dialog._host.repo.close()


def test_empty_number_warns(tmp_path: Path, qtbot, monkeypatch):
    dialog, fetched, batches, message_box = _import_dialog(tmp_path, qtbot)
    warnings: list[str] = []
    monkeypatch.setattr(
        message_box,
        "warning",
        lambda *args, **kwargs: warnings.append(args[2]),
    )
    dialog.number_edit.setPlainText("  \n")
    dialog._fetch_by_number()
    assert warnings == ["Введите номер"]
    assert fetched == []
    assert batches == []
    dialog._host.repo.close()
