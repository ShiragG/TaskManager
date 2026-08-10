from pathlib import Path

import pytest

from taskmanager.domain import WorkflowStatus, workflow_status_label
from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.services.settings_service import Settings, SettingsStore
from taskmanager.services.task_service import CreateTaskRequest, TaskService
from taskmanager.ui.main_window import COL_NUMBER, COL_STATUS, MainWindow


pytest.importorskip("PySide6")


@pytest.fixture
def app_env(tmp_path: Path, qtbot):
    work = tmp_path / "work"
    work.mkdir()
    settings_path = tmp_path / "settings.json"
    store = SettingsStore(settings_path)
    settings = Settings(work_dir=str(work))
    store.save(settings)
    repo = SqliteRepository(tmp_path / "ui.db")
    service = TaskService(repo, settings)
    window = MainWindow(service, settings, store)
    qtbot.addWidget(window)
    yield window, service
    repo.close()


def test_main_window_creates_project_and_task(app_env, qtbot):
    window, service = app_env
    project = service.create_project("UIDir")
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="1",
            description="ui smoke",
        )
    )
    window.reload_projects()
    assert window.tabs.count() == 1
    assert window.tabs.tabText(0) == "UIDir"
    table = window.tabs.widget(0)
    assert table.rowCount() == 1
    assert table.item(0, 1).text() == "1"
    assert window.tabs.tabBar().isMovable()


def test_tab_reorder_persists(app_env, qtbot):
    window, service = app_env
    service.create_project("First")
    service.create_project("Second")
    window.reload_projects()
    assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == [
        "First",
        "Second",
    ]
    window.tabs.tabBar().moveTab(0, 1)
    names = [p.name for p in service.list_projects()]
    assert names == ["Second", "First"]
    window.reload_projects()
    assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == [
        "Second",
        "First",
    ]


def test_delete_key_removes_selected_tasks(app_env, qtbot, monkeypatch):
    from PySide6.QtGui import QKeySequence, QShortcut
    from PySide6.QtWidgets import QMessageBox

    window, service = app_env
    project = service.create_project("DelDir")
    service.create_task(
        CreateTaskRequest(project_id=project.id, number="1", description="a")
    )
    service.create_task(
        CreateTaskRequest(project_id=project.id, number="2", description="b")
    )
    window.reload_projects()
    table = window.current_table()
    assert table is not None
    assert table.rowCount() == 2
    table.selectRow(0)
    table.setFocus()

    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes
    )
    shortcuts = [
        s
        for s in table.findChildren(QShortcut)
        if s.key().matches(QKeySequence.StandardKey.Delete)
        == QKeySequence.SequenceMatch.ExactMatch
    ]
    assert shortcuts, "Delete shortcut should be bound to the task table"
    shortcuts[0].activated.emit()
    assert table.rowCount() == 1
    assert len(service.list_tasks(project.id)) == 1


def test_copy_selected_task_number(app_env, qtbot):
    from PySide6.QtWidgets import QApplication

    window, service = app_env
    project = service.create_project("CopyDir")
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="42-ABC",
            description="copy number",
        )
    )
    window.reload_projects()
    table = window.tabs.widget(0)
    table.selectRow(0)
    window.copy_selected_task_number()
    assert QApplication.clipboard().text() == "42-ABC"
    assert "Номер скопирован" in window.statusBar().currentMessage()


def test_modules_dialog_no_default_razr(tmp_path: Path, qtbot):
    import taskmanager.ui.source_modules_settings as sms
    from PySide6.QtWidgets import QLabel

    from taskmanager.services.source_host import SourceHost
    from taskmanager.ui.source_modules_dialog import SourceModulesSettingsDialog
    from taskmanager.ui.source_modules_settings import HINT_TEXT

    work = tmp_path / "work"
    work.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    settings = Settings(work_dir=str(work))
    store.save(settings)
    repo = SqliteRepository(tmp_path / "ui-mod.db")
    service = TaskService(repo, settings)
    host = SourceHost(repo, settings, service, modules_base=tmp_path)

    dialog = SourceModulesSettingsDialog(settings, store, host)
    qtbot.addWidget(dialog)
    hint_texts = [
        lb.text() for lb in dialog.findChildren(QLabel) if HINT_TEXT[:40] in lb.text()
    ]
    assert hint_texts, "hint label should be present outside the scroll list"
    assert dialog._modules_widget.collect_configs() == []
    assert not hasattr(sms, "DEFAULT_RAZR_GITHUB")
    repo.close()


def test_import_dialog_empty_catalog_allows_list(tmp_path: Path, qtbot, monkeypatch):
    from taskmanager.services.source_host import ModuleCatalogCache, SourceHost
    from taskmanager.services.source_protocol import SourceListPage
    from taskmanager.services.settings_service import SourceModuleConfig
    from taskmanager.ui.source_import_dialog import SourceImportDialog

    work = tmp_path / "work"
    work.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    settings = Settings(work_dir=str(work))
    store.save(settings)
    repo = SqliteRepository(tmp_path / "ui-import.db")
    service = TaskService(repo, settings)
    host = SourceHost(repo, settings, service, modules_base=tmp_path)

    class _EmptyMod:
        id = "empty"
        display_name = "Empty"
        version = "1"
        api_version = "1"

        def configure(self, *, login, password):
            return None

        def list_statuses(self):
            return []

        def list_priorities(self):
            return []

        def list_items(self, page=1, status_filters=None):
            return SourceListPage(items=[], page=page)

        def get_item(self, external_id):
            raise AssertionError("unused")

        def download_files(self, *a, **k):
            return []

    host._by_id["empty"] = type(
        "L",
        (),
        {
            "config": SourceModuleConfig(
                module_id="empty", display_name="Empty", enabled=True
            ),
            "manifest": None,
            "module": _EmptyMod(),
            "load_error": None,
        },
    )()
    host._catalogs["empty"] = ModuleCatalogCache(statuses=[], priorities=[], error=None)
    monkeypatch.setattr(host, "get_credentials", lambda mid: ("u", "p"))

    dialog = SourceImportDialog(host)
    qtbot.addWidget(dialog)
    assert dialog._catalog_error is None
    assert "нет данных" in dialog.status_btn.text().lower()
    assert dialog.status_btn.isEnabled()
    dialog._load_list()
    assert dialog.hint.text() == "Нет данных"
    repo.close()


def test_import_dialog_scroll_appends_pages(tmp_path: Path, qtbot, monkeypatch):
    from taskmanager.services.source_host import ModuleCatalogCache, SourceHost
    from taskmanager.services.source_protocol import SourceItemSummary, SourceListPage
    from taskmanager.services.settings_service import SourceModuleConfig
    from taskmanager.ui.source_import_dialog import SourceImportDialog

    work = tmp_path / "work"
    work.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    settings = Settings(work_dir=str(work))
    store.save(settings)
    repo = SqliteRepository(tmp_path / "ui-scroll.db")
    service = TaskService(repo, settings)
    host = SourceHost(repo, settings, service, modules_base=tmp_path)
    calls: list[int] = []

    class _PagedMod:
        id = "paged"
        display_name = "Paged"
        version = "1"
        api_version = "1"

        def configure(self, *, login, password):
            return None

        def list_statuses(self):
            return []

        def list_priorities(self):
            return []

        def list_items(self, page=1, status_filters=None):
            calls.append(page)
            if page == 1:
                items = [
                    SourceItemSummary(external_id="1", title="A"),
                    SourceItemSummary(external_id="2", title="B"),
                ]
                return SourceListPage(items=items, page=1, has_more=True)
            if page == 2:
                items = [SourceItemSummary(external_id="3", title="C")]
                return SourceListPage(items=items, page=2, has_more=False)
            return SourceListPage(items=[], page=page, has_more=False)

        def get_item(self, external_id):
            raise AssertionError("unused")

        def download_files(self, *a, **k):
            return []

    host._by_id["paged"] = type(
        "L",
        (),
        {
            "config": SourceModuleConfig(
                module_id="paged", display_name="Paged", enabled=True
            ),
            "manifest": None,
            "module": _PagedMod(),
            "load_error": None,
        },
    )()
    host._catalogs["paged"] = ModuleCatalogCache(statuses=[], priorities=[], error=None)
    monkeypatch.setattr(host, "get_credentials", lambda mid: ("u", "p"))

    dialog = SourceImportDialog(host)
    qtbot.addWidget(dialog)
    dialog._load_list()
    assert calls == [1]
    assert dialog.list_widget.count() == 2
    assert dialog._has_more is True
    assert dialog._page == 1

    # Direct append path (scroll needs a tall viewport to fire valueChanged).
    dialog._fetch_list_page(page=2, append=True)
    assert calls == [1, 2]
    assert dialog.list_widget.count() == 3
    assert dialog._has_more is False

    # No further loads while has_more is false / loading guard.
    dialog._loading = False
    dialog._on_list_scroll(dialog.list_widget.verticalScrollBar().maximum())
    assert calls == [1, 2]

    # Reload replaces from page 1.
    dialog._load_list()
    assert calls == [1, 2, 1]
    assert dialog.list_widget.count() == 2
    repo.close()


def test_import_dialog_checkboxes_and_already_imported(tmp_path: Path, qtbot, monkeypatch):
    from PySide6.QtCore import Qt

    from taskmanager.services.source_host import ModuleCatalogCache, SourceHost
    from taskmanager.services.source_protocol import SourceItemSummary, SourceListPage
    from taskmanager.services.settings_service import SourceModuleConfig
    from taskmanager.ui.source_import_dialog import SourceImportDialog

    work = tmp_path / "work"
    work.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    settings = Settings(work_dir=str(work))
    store.save(settings)
    repo = SqliteRepository(tmp_path / "ui-import-chk.db")
    service = TaskService(repo, settings)
    project = service.create_project("Imp")
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="imported",
            description="",
            create_folder=False,
            source_module_id="chk",
            external_id="2",
        )
    )
    host = SourceHost(repo, settings, service, modules_base=tmp_path)

    class _Mod:
        id = "chk"
        display_name = "Chk"
        version = "1"
        api_version = "1"

        def configure(self, *, login, password):
            return None

        def list_statuses(self):
            return []

        def list_priorities(self):
            return []

        def list_items(self, page=1, status_filters=None):
            return SourceListPage(
                items=[
                    SourceItemSummary(external_id="1", title="New"),
                    SourceItemSummary(external_id="2", title="Done"),
                    SourceItemSummary(external_id="3", title="Also"),
                ],
                page=1,
                has_more=False,
            )

        def get_item(self, external_id):
            raise AssertionError("unused")

        def download_files(self, *a, **k):
            return []

    host._by_id["chk"] = type(
        "L",
        (),
        {
            "config": SourceModuleConfig(
                module_id="chk", display_name="Chk", enabled=True
            ),
            "manifest": None,
            "module": _Mod(),
            "load_error": None,
        },
    )()
    host._catalogs["chk"] = ModuleCatalogCache(statuses=[], priorities=[], error=None)
    monkeypatch.setattr(host, "get_credentials", lambda mid: ("u", "p"))

    dialog = SourceImportDialog(host, project_id=project.id)
    qtbot.addWidget(dialog)
    dialog._load_list()
    assert dialog.list_widget.count() == 3

    item_new = dialog.list_widget.item(0)
    item_done = dialog.list_widget.item(1)
    item_also = dialog.list_widget.item(2)

    assert item_new.flags() & Qt.ItemFlag.ItemIsUserCheckable
    assert item_new.flags() & Qt.ItemFlag.ItemIsEnabled
    assert item_new.checkState() == Qt.CheckState.Unchecked

    assert not (item_done.flags() & Qt.ItemFlag.ItemIsEnabled)
    assert item_done.checkState() == Qt.CheckState.Checked

    dialog._select_all_selectable()
    assert item_new.checkState() == Qt.CheckState.Checked
    assert item_also.checkState() == Qt.CheckState.Checked
    assert item_done.checkState() == Qt.CheckState.Checked
    assert dialog._selectable_checked_ids() == ["1", "3"]
    assert dialog.import_btn.isEnabled()
    repo.close()


def test_module_row_has_auth_check_button(tmp_path: Path, qtbot):
    from PySide6.QtWidgets import QPushButton

    from taskmanager.services.source_host import SourceHost
    from taskmanager.services.settings_service import SourceModuleConfig
    from taskmanager.ui.source_modules_settings import SourceModulesSettingsWidget

    work = tmp_path / "work"
    work.mkdir()
    settings = Settings(work_dir=str(work))
    repo = SqliteRepository(tmp_path / "ui-auth.db")
    service = TaskService(repo, settings)
    host = SourceHost(repo, settings, service, modules_base=tmp_path)
    host._by_id["m"] = type(
        "L",
        (),
        {
            "config": SourceModuleConfig(module_id="m", display_name="M", enabled=True),
            "manifest": None,
            "module": None,
            "load_error": None,
        },
    )()

    widget = SourceModulesSettingsWidget(host)
    qtbot.addWidget(widget)
    labels = [
        b.text()
        for b in widget.findChildren(QPushButton)
        if b.text() == "Проверить вход"
    ]
    assert labels
    repo.close()


def test_context_menu_preserves_multi_selection(app_env, qtbot):
    from PySide6.QtCore import QItemSelectionModel

    from taskmanager.ui.main_window import TASK_ID_ROLE

    window, service = app_env
    project = service.create_project("CtxSel")
    service.create_task(
        CreateTaskRequest(project_id=project.id, number="1", create_folder=False)
    )
    service.create_task(
        CreateTaskRequest(project_id=project.id, number="2", create_folder=False)
    )
    window.reload_projects()
    table = window.current_table()
    assert table is not None
    table.selectRow(0)
    model = table.selectionModel()
    assert model is not None
    model.select(
        table.model().index(1, 0),
        QItemSelectionModel.SelectionFlag.Rows
        | QItemSelectionModel.SelectionFlag.Select,
    )
    assert len(window.selected_task_ids()) == 2

    # Right-click on an already-selected row must not collapse multi-select
    window._ensure_context_row_selected(table, table.model().index(1, COL_NUMBER))
    assert len(window.selected_task_ids()) == 2

    # Clicking a row outside the selection replaces selection with that row
    table.clearSelection()
    table.selectRow(0)
    assert len(window.selected_task_ids()) == 1
    window._ensure_context_row_selected(table, table.model().index(1, COL_NUMBER))
    assert window.selected_task_ids() == [
        int(table.item(1, COL_NUMBER).data(TASK_ID_ROLE))
    ]


def test_delete_disabled_in_archive_mode(app_env, qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    window, service = app_env
    project = service.create_project("ArchDel")
    task = service.create_task(
        CreateTaskRequest(project_id=project.id, number="9", create_folder=False)
    )
    service.archive_task(task.id)
    window.reload_projects()
    window.archive_cb.setChecked(True)
    assert not window.act_delete.isEnabled()
    assert not window.act_delete.isVisible()

    table = window.current_table()
    assert table is not None
    table.selectRow(0)
    prompts: list[str] = []

    def capture_info(*a, **k):
        prompts.append(a[2] if len(a) > 2 else "")
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "information", capture_info)
    window.delete_selected_task()
    assert prompts
    assert "архив" in prompts[0].lower()
    assert service.get_task(task.id).is_archived


def test_multi_color_applies_to_all_selected(app_env, qtbot):
    window, service = app_env
    project = service.create_project("Colors")
    t1 = service.create_task(
        CreateTaskRequest(project_id=project.id, number="1", create_folder=False)
    )
    t2 = service.create_task(
        CreateTaskRequest(project_id=project.id, number="2", create_folder=False)
    )
    window.reload_projects()
    table = window.current_table()
    assert table is not None
    from PySide6.QtCore import QItemSelectionModel

    table.selectRow(0)
    model = table.selectionModel()
    assert model is not None
    model.select(
        table.model().index(1, 0),
        QItemSelectionModel.SelectionFlag.Rows
        | QItemSelectionModel.SelectionFlag.Select,
    )
    window._apply_color_to_selection("#ff0000")
    assert service.get_task(t1.id).color == "#ff0000"
    assert service.get_task(t2.id).color == "#ff0000"


def test_status_column_workflow_vs_source(app_env, qtbot):
    window, service = app_env
    project = service.create_project("StatusCol")
    local = service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="L1",
            create_folder=False,
            workflow_status=WorkflowStatus.IN_PROGRESS,
        )
    )
    sourced = service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="S1",
            create_folder=False,
            source_module_id="fake",
            external_id="99",
            source_label="Fake",
            source_status_id="10",
            source_status_label="НАЗНАЧЕНО",
            workflow_status=WorkflowStatus.NEW,
        )
    )
    window.reload_projects()
    table = window.current_table()
    assert table is not None
    by_number = {
        table.item(r, COL_NUMBER).text(): table.item(r, COL_STATUS).text()
        for r in range(table.rowCount())
    }
    assert by_number["L1"] == workflow_status_label(WorkflowStatus.IN_PROGRESS)
    assert by_number["S1"] == "НАЗНАЧЕНО"
    assert local.display_status == "В работе"
    assert sourced.display_status == "НАЗНАЧЕНО"
