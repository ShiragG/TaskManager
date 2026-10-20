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


def test_reload_projects_fills_only_current_tab(app_env, qtbot, monkeypatch):
    window, service = app_env
    first = service.create_project("First")
    second = service.create_project("Second")
    service.create_task(
        CreateTaskRequest(project_id=first.id, number="1", create_folder=False)
    )
    service.create_task(
        CreateTaskRequest(project_id=second.id, number="2", create_folder=False)
    )
    filled: list[str] = []
    original = window._fill_table

    def spy(table, project):
        filled.append(project.name)
        return original(table, project)

    monkeypatch.setattr(window, "_fill_table", spy)
    window.reload_projects()
    assert window.tabs.count() == 2
    assert filled == [window.tabs.tabText(window.tabs.currentIndex())]
    other = 1 if window.tabs.currentIndex() == 0 else 0
    window.tabs.setCurrentIndex(other)
    assert window.tabs.tabText(other) in filled
    assert filled.count(window.tabs.tabText(other)) >= 1


def test_plain_cell_is_truncated(app_env, qtbot):
    from taskmanager.ui.main_window import COL_DESCRIPTION

    window, service = app_env
    project = service.create_project("Long")
    long_text = "x" * 200
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="1",
            description=long_text,
            create_folder=False,
        )
    )
    window.reload_projects()
    table = window.tabs.widget(0)
    cell = table.item(0, COL_DESCRIPTION).text()
    assert cell.endswith("...")
    assert len(cell) == 123
    assert service.get_task(service.list_tasks(project.id)[0].id).description_plain == long_text


def test_project_table_sort_restored_after_rebuild(app_env, qtbot):
    from PySide6.QtCore import Qt

    from taskmanager.ui.main_window import COL_NUMBER, COL_PRIORITY

    window, service = app_env
    project = service.create_project("Sort")
    service.create_task(
        CreateTaskRequest(
            project_id=project.id, number="2", priority=1, create_folder=False
        )
    )
    service.create_task(
        CreateTaskRequest(
            project_id=project.id, number="1", priority=9, create_folder=False
        )
    )
    window.reload_projects()
    header = window.current_table().horizontalHeader()
    assert header.sortIndicatorSection() == COL_NUMBER
    assert header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder

    header.setSortIndicator(COL_PRIORITY, Qt.SortOrder.DescendingOrder)
    window.reload_projects()
    header = window.current_table().horizontalHeader()
    assert header.sortIndicatorSection() == COL_PRIORITY
    assert header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
    stored = next(item for item in service.list_projects() if item.name == "Sort")
    assert stored.table_sort_column == "priority"
    assert stored.table_sort_direction == "desc"

    window._show_hidden = True
    window.reload_projects()
    header = window.current_table().horizontalHeader()
    assert header.sortIndicatorSection() == COL_PRIORITY
    assert header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder


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


def test_context_menu_source_section_for_multi_selection(app_env, qtbot, monkeypatch):
    from taskmanager.ui import main_window as mw_mod

    class FakeMenu:
        def __init__(self, *a, **k):
            self.labels: list[str] = []

        def addAction(self, *a, **k):
            self.labels.append(a[0] if a else "")
            return None

        def addSeparator(self):
            return None

        def addMenu(self, title):
            sub = FakeMenu()
            sub.labels.append(title)
            return sub

        def exec(self, *_a, **_k):
            return None

    captured: dict[str, FakeMenu] = {}

    def fake_factory(*a, **k):
        menu = FakeMenu()
        captured["menu"] = menu
        return menu

    monkeypatch.setattr(mw_mod, "QMenu", fake_factory)
    window, service = app_env
    project = service.create_project("CtxSrc")
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="1",
            create_folder=False,
            source_module_id="m",
            external_id="x1",
            source_label="M",
        )
    )
    service.create_task(
        CreateTaskRequest(project_id=project.id, number="2", create_folder=False)
    )
    window.reload_projects()
    table = window.current_table()
    from PySide6.QtCore import QItemSelectionModel

    table.selectRow(0)
    model = table.selectionModel()
    model.select(
        table.model().index(1, 0),
        QItemSelectionModel.SelectionFlag.Rows
        | QItemSelectionModel.SelectionFlag.Select,
    )
    assert len(window.selected_task_ids()) == 2
    pos = table.visualItemRect(table.item(1, COL_NUMBER)).center()
    window._show_context_menu(table, pos)
    menu = captured["menu"]
    assert "Обновить из источника…" in menu.labels
    assert "Скачать файлы источника…" in menu.labels


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


def test_number_column_sorts_naturally(app_env, qtbot):
    from PySide6.QtCore import Qt

    window, service = app_env
    project = service.create_project("NatSort")
    for number in ("10а", "2", "10", "2а", "INC-10", "INC-9"):
        service.create_task(
            CreateTaskRequest(
                project_id=project.id, number=number, create_folder=False
            )
        )
    window.reload_projects()
    table = window.current_table()
    assert table is not None
    table.sortItems(COL_NUMBER, Qt.SortOrder.AscendingOrder)
    numbers = [table.item(r, COL_NUMBER).text() for r in range(table.rowCount())]
    assert numbers == ["2", "2а", "10", "10а", "INC-9", "INC-10"]


def test_settings_dialog_tabs_and_event_defaults(app_env, qtbot):
    from PySide6.QtWidgets import QTabWidget

    from taskmanager.ui.settings_dialog import SettingsDialog

    window, _service = app_env
    dialog = SettingsDialog(window.settings, window.settings_store, window)
    qtbot.addWidget(dialog)
    tabs = dialog.findChildren(QTabWidget)
    assert tabs
    tab = tabs[0]
    titles = [tab.tabText(i) for i in range(tab.count())]
    assert titles == ["Общие", "Заявки", "События", "Горячие клавиши"]
    assert dialog.event_sound_cb.isChecked()
    assert dialog.event_os_notification_cb.isChecked()
    assert dialog.snooze_combo.currentData() == 15
    assert dialog._update_panel.isHidden()
    assert dialog.check_updates_on_startup_cb.isChecked()
    assert dialog.image_preview_combo.currentData() == 480
    assert dialog.show_in_tray_cb.isChecked()
    labels = [
        dialog.image_preview_combo.itemText(i)
        for i in range(dialog.image_preview_combo.count())
    ]
    assert labels == ["Уменьшенная", "Средняя", "Исходная"]
    hint = dialog.image_click_hint.text()
    assert "Ctrl+ЛКМ" in hint
    assert "исходн" in hint.lower()


def test_quiet_update_check_skips_uptodate_modal(app_env, qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from taskmanager.services.update_service import LatestRelease
    from taskmanager.version import get_version

    window, _service = app_env
    boxes: list[str] = []

    def capture_info(*_a, **_k):
        boxes.append("info")
        return QMessageBox.StandardButton.Ok

    def capture_warn(*_a, **_k):
        boxes.append("warn")
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "information", capture_info)
    monkeypatch.setattr(QMessageBox, "warning", capture_warn)
    current = get_version()
    tag = current if current.lower().startswith("v") else f"v{current}"
    release = LatestRelease(tag=tag, version=current, assets=[])
    monkeypatch.setattr(
        "taskmanager.ui.update_worker.UpdateService.fetch_latest_release",
        lambda self: release,
    )
    window.start_update_check(quiet=True)
    assert window._update_panel.isHidden()
    assert "Проверка обновлений" not in window.statusBar().currentMessage()
    qtbot.waitUntil(lambda: not window._update_busy, timeout=5000)
    assert boxes == []
    assert window._update_panel.isHidden()
    assert "Проверка обновлений" not in window.statusBar().currentMessage()
    assert window.statusBar().currentMessage() == ""


def test_quiet_module_update_check_hides_ui_when_nothing_to_download(
    app_env, qtbot, monkeypatch
):
    from taskmanager.services.module_install import ModuleLatestRelease
    from taskmanager.services.settings_service import SourceModuleConfig

    window, _service = app_env

    class _Host:
        def enabled_modules_with_github(self):
            return [
                SourceModuleConfig(
                    module_id="fake",
                    enabled=True,
                    github_repo="owner/fake",
                    installed_version="1.0.0",
                    display_name="Fake",
                )
            ]

    window.source_host = _Host()
    monkeypatch.setattr(
        "taskmanager.ui.update_worker.fetch_latest_module_release",
        lambda _repo: ModuleLatestRelease(tag="v1.0.0", version="1.0.0", assets=[]),
    )
    window.start_module_update_check(quiet=True)
    assert window._update_panel.isHidden()
    assert "Проверка обновлений модулей" not in window.statusBar().currentMessage()
    qtbot.waitUntil(lambda: not window._update_busy, timeout=5000)
    assert window._update_panel.isHidden()
    assert "Проверка обновлений модулей" not in window.statusBar().currentMessage()
    assert window.statusBar().currentMessage() == ""


def test_module_updates_skipped_when_app_update_in_flight(app_env, qtbot):
    from pathlib import Path

    window, _service = app_env
    window._update_busy = True
    assert window.should_skip_module_updates()
    window.start_module_update_check(quiet=True)

    window._update_busy = False
    window._pending_update_path = Path("/tmp/TaskManager.new")
    assert window.should_skip_module_updates()
    window.start_module_update_check(quiet=True)

    window._pending_update_path = None
    window._skip_module_updates_this_session = True
    assert window.should_skip_module_updates()
    window.start_module_update_check(quiet=True)


def test_settings_close_copies_install_banner(app_env, qtbot):
    from pathlib import Path

    from taskmanager.ui.settings_dialog import SettingsDialog

    window, _service = app_env
    window.show()
    window._pending_update_path = Path("/tmp/TaskManager.new")
    dialog = SettingsDialog(window.settings, window.settings_store, window)
    qtbot.addWidget(dialog)
    dialog.show()
    window._update_ui = dialog
    dialog._update_panel.show()
    dialog._update_label.setText("Обновление готово. «Установить и закрыть»")
    dialog._update_progress.hide()
    dialog._update_cancel_btn.hide()
    dialog._update_restart_btn.show()
    window._on_settings_finished(0)
    assert not window._update_panel.isHidden()
    assert not window._update_restart_btn.isHidden()
    assert "Установить и закрыть" in window._update_label.text()


def test_settings_dialog_keep_priority_on_source_refresh_saves(app_env, qtbot):
    from taskmanager.ui.settings_dialog import SettingsDialog

    window, _service = app_env
    dialog = SettingsDialog(window.settings, window.settings_store, window)
    qtbot.addWidget(dialog)
    assert dialog.keep_priority_on_source_refresh_cb.text() == (
        "Не изменять приоритет при обновлении из источника"
    )
    assert not dialog.keep_priority_on_source_refresh_cb.isChecked()
    dialog.keep_priority_on_source_refresh_cb.setChecked(True)
    dialog._save()
    loaded = window.settings_store.load()
    assert loaded.keep_priority_on_source_refresh is True
    assert window.settings.keep_priority_on_source_refresh is True


def test_settings_dialog_saves_image_size_and_tray(app_env, qtbot):
    from taskmanager.ui.settings_dialog import SettingsDialog

    window, _service = app_env
    dialog = SettingsDialog(window.settings, window.settings_store, window)
    qtbot.addWidget(dialog)
    small_idx = dialog.image_preview_combo.findData(240)
    assert small_idx >= 0
    dialog.image_preview_combo.setCurrentIndex(small_idx)
    dialog.show_in_tray_cb.setChecked(False)
    dialog._save()
    loaded = window.settings_store.load()
    assert loaded.image_preview_width == 240
    assert loaded.show_in_tray is False


def test_tray_menu_actions_and_trigger_shows_window(app_env, qtbot):
    from PySide6.QtWidgets import QSystemTrayIcon

    window, _service = app_env
    tray = window._reminder_tray
    assert tray is not None
    menu = tray.contextMenu()
    assert menu is not None
    labels = [action.text() for action in menu.actions() if not action.isSeparator()]
    assert labels == ["Открыть", "Календарь", "Настройки", "Закрыть"]
    window.showMinimized()
    tray.activated.emit(QSystemTrayIcon.ActivationReason.Trigger)
    assert window.isVisible()
    assert not window.isMinimized()


def test_close_event_quits_even_with_tray(app_env, qtbot, monkeypatch):
    from PySide6.QtWidgets import QApplication

    window, _service = app_env
    window.settings.show_in_tray = True
    window.show()
    quits: list[bool] = []
    monkeypatch.setattr(QApplication, "quit", lambda *_a, **_k: quits.append(True))
    window.close()
    assert not window.isVisible()
    assert quits == [True]


def test_status_mark_icon_is_a_circle(qtbot):
    from taskmanager.ui.main_window import status_mark_icon

    icon = status_mark_icon("#ff00ff")
    assert not icon.isNull()
    image = icon.pixmap(16, 16).toImage()
    corner = image.pixelColor(0, 0)
    center = image.pixelColor(image.width() // 2, image.height() // 2)
    assert corner.alpha() == 0
    assert center.alpha() > 200
    assert center.name() == "#ff00ff"
    assert status_mark_icon("nope").isNull()


def test_status_results_fade_progress_holds(app_env, qtbot, monkeypatch):
    from PySide6.QtWidgets import QLabel

    monkeypatch.setattr("taskmanager.ui.main_window.STATUS_RESULT_MS", 80)
    window, _service = app_env
    label = window.statusBar().findChild(QLabel, "selectionCount")
    assert window.statusBar().currentMessage() == ""
    assert label.text() == "Заявок: 0"

    window._status_result("Номер скопирован")
    window._status_progress("Импорт: 1 из 2")
    qtbot.wait(200)
    assert window.statusBar().currentMessage() == "Импорт: 1 из 2"
    assert label.text() == "Заявок: 0"

    window._status_result("Импорт завершён: создано 2")
    assert window.statusBar().currentMessage() == "Импорт завершён: создано 2"
    qtbot.waitUntil(lambda: window.statusBar().currentMessage() == "", timeout=2000)
    assert label.text() == "Заявок: 0"


def test_selection_counter_follows_current_list(app_env, qtbot):
    from PySide6.QtCore import QItemSelectionModel
    from PySide6.QtWidgets import QLabel

    from taskmanager.services.task_service import UpdateTaskRequest

    window, service = app_env
    project = service.create_project("Count")
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="1",
            description="needle",
            create_folder=False,
        )
    )
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="2",
            description="other",
            create_folder=False,
        )
    )
    archived = service.create_task(
        CreateTaskRequest(
            project_id=project.id, number="3", description="old", create_folder=False
        )
    )
    service.archive_task(archived.id)
    hidden = service.create_task(
        CreateTaskRequest(
            project_id=project.id, number="4", description="hide", create_folder=False
        )
    )
    service.update_task(hidden.id, UpdateTaskRequest(hidden=True))
    other = service.create_project("Other")
    service.create_task(
        CreateTaskRequest(
            project_id=other.id, number="9", description="elsewhere", create_folder=False
        )
    )
    window.reload_projects()
    label = window.statusBar().findChild(QLabel, "selectionCount")
    assert label is window._selection_count
    assert window.statusBar().currentMessage() == ""
    assert label.text() == "Заявок: 2"

    window.statusBar().showMessage("Номер скопирован")
    table = window.current_table()
    assert table is not None
    table.selectRow(0)
    assert window.statusBar().currentMessage() == "Номер скопирован"
    assert label.text() == "Выделено 1 из 2"
    model = table.selectionModel()
    assert model is not None
    model.select(
        table.model().index(1, 0),
        QItemSelectionModel.SelectionFlag.Rows
        | QItemSelectionModel.SelectionFlag.Select,
    )
    assert label.text() == "Выделено 2 из 2"
    table.clearSelection()
    assert label.text() == "Заявок: 2"
    assert window.statusBar().currentMessage() == "Номер скопирован"

    window.search_edit.setText("needle")
    assert label.text() == "Заявок: 1"
    window.search_edit.setText("")
    assert label.text() == "Заявок: 2"

    window.archive_cb.setChecked(True)
    assert label.text() == "Заявок: 1"
    window.archive_cb.setChecked(False)
    window.hidden_cb.setChecked(True)
    assert label.text() == "Заявок: 1"
    window.hidden_cb.setChecked(False)
    assert label.text() == "Заявок: 2"

    window.tabs.setCurrentIndex(1)
    assert window.tabs.tabText(1) == "Other"
    assert label.text() == "Заявок: 1"
    window.tabs.setCurrentIndex(0)
    assert label.text() == "Заявок: 2"
    assert window.statusBar().currentMessage() == "Номер скопирован"


def test_row_paints_task_color_priority_status_mark_and_deadline(app_env, qtbot):
    from datetime import date, timedelta

    from taskmanager.domain import contrast_foreground, priority_color_hex
    from taskmanager.services.settings_service import SourceStatusHighlight
    from taskmanager.ui.main_window import COL_DATE, COL_DESCRIPTION, COL_PRIORITY, COL_STATUS

    window, service = app_env
    window.settings.warning_color = "#0000ff"
    window.settings.highlight_warnings = True
    window.settings.warning_lead_days = 1
    window.settings.show_priority_colors = True
    window.settings.source_status_highlights = {
        "fake": SourceStatusHighlight(
            enabled=True,
            colors={"10": "#ff00ff", "99": "#123456"},
            labels={"10": "НАЗНАЧЕНО", "99": "Архивный"},
        )
    }
    project = service.create_project("Paint")
    today = date.today()
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="L1",
            priority=10,
            date_end=today,
            create_folder=False,
            workflow_status=WorkflowStatus.IN_PROGRESS,
        )
    )
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="S1",
            priority=0,
            color="#ffff00",
            date_end=today,
            create_folder=False,
            source_module_id="fake",
            external_id="1",
            source_label="Fake",
            source_status_id="10",
            source_status_label="НАЗНАЧЕНО",
        )
    )
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="S2",
            priority=10,
            color="#00ff00",
            date_end=today + timedelta(days=30),
            create_folder=False,
            source_module_id="fake",
            external_id="2",
            source_label="Fake",
            source_status_id="11",
            source_status_label="Без цвета",
        )
    )
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="S4",
            create_folder=False,
            source_module_id="fake",
            external_id="4",
            source_label="Fake",
            source_status_id="99",
            source_status_label="Архивный",
        )
    )
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="S5",
            create_folder=False,
            source_module_id="other",
            external_id="5",
            source_label="Other",
            source_status_id="10",
            source_status_label="НАЗНАЧЕНО",
        )
    )
    window.reload_projects()
    table = window.current_table()
    assert table is not None

    def cell(number: str, column: int):
        for row in range(table.rowCount()):
            if table.item(row, COL_NUMBER).text() == number:
                return table.item(row, column)
        raise AssertionError(number)

    local_priority = cell("L1", COL_PRIORITY)
    local_status = cell("L1", COL_STATUS)
    local_date = cell("L1", COL_DATE)
    assert local_status.icon().isNull()
    assert local_date.foreground().color().name() == "#0000ff"
    assert local_priority.foreground().color().name() == contrast_foreground(
        priority_color_hex(10)
    )
    assert local_priority.foreground().color().name() != "#0000ff"

    marked = cell("S1", COL_STATUS)
    marked_date = cell("S1", COL_DATE)
    marked_priority = cell("S1", COL_PRIORITY)
    marked_description = cell("S1", COL_DESCRIPTION)
    assert not marked.icon().isNull()
    assert marked.background().color().name() == "#ffff00"
    assert marked.background().color().name() != "#ff00ff"
    assert marked_date.background().color().name() == "#ffff00"
    assert marked_date.foreground().color().name() == "#0000ff"
    assert marked_description.foreground().color().name() == contrast_foreground("#ffff00")
    assert marked_description.foreground().color().name() != "#0000ff"
    assert marked_priority.background().color().name() == priority_color_hex(0)
    assert marked_priority.foreground().color().name() == contrast_foreground(
        priority_color_hex(0)
    )
    assert marked_priority.foreground().color().name() != "#0000ff"

    plain_status = cell("S2", COL_STATUS)
    plain_date = cell("S2", COL_DATE)
    assert plain_status.icon().isNull()
    assert plain_date.foreground().color().name() == contrast_foreground("#00ff00")
    assert plain_date.foreground().color().name() != "#0000ff"
    assert not cell("S4", COL_STATUS).icon().isNull()
    assert cell("S5", COL_STATUS).icon().isNull()

    window.settings.source_status_highlights["fake"].enabled = False
    window.reload_current_tab()
    table = window.current_table()
    assert table is not None

    def cell_after(number: str, column: int):
        for row in range(table.rowCount()):
            if table.item(row, COL_NUMBER).text() == number:
                return table.item(row, column)
        raise AssertionError(number)

    assert cell_after("S1", COL_STATUS).icon().isNull()
    assert cell_after("S4", COL_STATUS).icon().isNull()
    assert cell_after("S1", COL_DATE).foreground().color().name() == "#0000ff"


def test_workflow_status_mark_only_on_tasks_without_source(app_env, qtbot):
    window, service = app_env
    window.settings.highlight_workflow_statuses = True
    window.settings.workflow_status_colors = {
        "in_progress": "#112233",
        "new": "#abcdef",
    }
    project = service.create_project("WorkColors")
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="L1",
            create_folder=False,
            workflow_status=WorkflowStatus.IN_PROGRESS,
        )
    )
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="L2",
            create_folder=False,
            workflow_status=WorkflowStatus.DONE,
        )
    )
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="S1",
            create_folder=False,
            workflow_status=WorkflowStatus.IN_PROGRESS,
            source_module_id="fake",
            external_id="1",
            source_label="Fake",
            source_status_id="10",
            source_status_label="НАЗНАЧЕНО",
        )
    )
    window.reload_projects()
    table = window.current_table()
    assert table is not None

    def cell(number: str):
        for row in range(table.rowCount()):
            if table.item(row, COL_NUMBER).text() == number:
                return table.item(row, COL_STATUS)
        raise AssertionError(number)

    def center(icon) -> str:
        image = icon.pixmap(16, 16).toImage()
        return image.pixelColor(image.width() // 2, image.height() // 2).name()

    marked = cell("L1")
    assert not marked.icon().isNull()
    assert center(marked.icon()) == "#112233"
    assert cell("L2").icon().isNull()
    assert cell("S1").icon().isNull()

    window.settings.highlight_workflow_statuses = False
    window.reload_current_tab()
    table = window.current_table()
    assert table is not None

    def cell_after(number: str):
        for row in range(table.rowCount()):
            if table.item(row, COL_NUMBER).text() == number:
                return table.item(row, COL_STATUS)
        raise AssertionError(number)

    assert cell_after("L1").icon().isNull()
    assert window.settings.workflow_status_colors["in_progress"] == "#112233"


def test_status_color_dialog_rows_reset_and_notice(qtbot):
    from taskmanager.ui.source_modules_dialog import (
        CATALOG_UNAVAILABLE,
        SourceStatusColorsDialog,
        status_color_rows,
    )

    rows = status_color_rows(
        [("10", "НАЗНАЧЕНО"), ("10", "дубль"), ("3", "  ")],
        {"10": "#FF0000", "99": "#00ff00"},
        {"10": "старое", "99": "Ушедший", "3": "запас"},
    )
    assert rows == [
        ("10", "НАЗНАЧЕНО", "#FF0000"),
        ("3", "запас", ""),
        ("99", "Ушедший", "#00ff00"),
    ]
    assert status_color_rows(
        [],
        {"99": "#00ff00"},
        {"99": "Ушедший", "3": "Без цвета"},
    ) == [
        ("99", "Ушедший", "#00ff00"),
        ("3", "Без цвета", ""),
    ]

    dialog = SourceStatusColorsDialog(rows, catalog_unavailable=True)
    qtbot.addWidget(dialog)
    assert not dialog.notice.isHidden()
    assert dialog.notice.text() == CATALOG_UNAVAILABLE
    editor = dialog._editors[0]
    assert editor.color == "#ff0000"
    editor.reset_btn.click()
    assert editor.color == ""
    colors, labels = dialog.collect()
    assert "10" not in colors
    assert labels["10"] == "НАЗНАЧЕНО"
    assert colors["99"] == "#00ff00"
    assert labels["3"] == "запас"

    fresh = SourceStatusColorsDialog(
        [("1", "A", "")], catalog_unavailable=False
    )
    qtbot.addWidget(fresh)
    assert fresh.notice.isHidden()


def test_status_color_pick_sets_swatch(qtbot, monkeypatch):
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QColorDialog

    from taskmanager.ui.source_modules_dialog import SourceStatusColorsDialog

    dialog = SourceStatusColorsDialog(
        [("10", "НАЗНАЧЕНО", "")], catalog_unavailable=False
    )
    qtbot.addWidget(dialog)
    monkeypatch.setattr(QColorDialog, "getColor", lambda *_a, **_k: QColor("#112233"))
    dialog._editors[0].swatch.click()
    assert dialog._editors[0].color == "#112233"
    colors, labels = dialog.collect()
    assert colors == {"10": "#112233"}
    assert labels == {"10": "НАЗНАЧЕНО"}


def test_module_card_status_highlights_survive_uninstall(tmp_path, qtbot, monkeypatch):
    from PySide6.QtWidgets import QCheckBox, QPushButton

    from taskmanager.services.settings_service import (
        SourceModuleConfig,
        SourceStatusHighlight,
        source_status_mark_color,
    )
    from taskmanager.services.source_host import SourceHost
    from taskmanager.services.source_protocol import SourceStatusOption
    from taskmanager.ui.source_modules_dialog import (
        SourceModulesSettingsDialog,
        SourceStatusColorsDialog,
    )
    from taskmanager.ui.source_modules_settings import SourceModulesSettingsWidget

    work = tmp_path / "work"
    work.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    settings = Settings(
        work_dir=str(work),
        source_status_highlights={
            "m": SourceStatusHighlight(
                enabled=True,
                colors={"1": "#aabbcc"},
                labels={"1": "Старое"},
            ),
            "gone": SourceStatusHighlight(
                enabled=True,
                colors={"9": "#010203"},
                labels={"9": "Чужой"},
            ),
        },
    )
    store.save(settings)
    repo = SqliteRepository(tmp_path / "ui-status-color.db")
    service = TaskService(repo, settings)
    host = SourceHost(repo, settings, service, modules_base=tmp_path)
    host._by_id["m"] = type(
        "L",
        (),
        {
            "config": SourceModuleConfig(
                module_id="m", display_name="M", enabled=False
            ),
            "manifest": None,
            "module": None,
            "load_error": None,
        },
    )()

    widget = SourceModulesSettingsWidget(host, settings=settings)
    qtbot.addWidget(widget)
    row = widget._rows[0]
    assert row.highlight_cb.text() == "Подсвечивать статусы"
    assert row.highlight_cb.isChecked()
    assert not row.enabled_cb.isChecked()
    assert row.status_colors_btn.isEnabled()
    assert any(
        box.text() == "Подсвечивать статусы" for box in widget.findChildren(QCheckBox)
    )
    assert any(
        button.text() == "Цвета статусов…" for button in widget.findChildren(QPushButton)
    )

    widget._add_blank()
    blank = widget._rows[-1]
    assert not blank.status_colors_btn.isEnabled()
    assert not blank.highlight_cb.isEnabled()

    monkeypatch.setattr(host, "status_catalog", lambda _mid: ([], "down"))

    def reject_exec(self):
        assert not self.notice.isHidden()
        assert [editor.status_id for editor in self._editors] == ["1"]
        assert self._editors[0].label_text == "Старое"
        return SourceStatusColorsDialog.DialogCode.Rejected

    monkeypatch.setattr(SourceStatusColorsDialog, "exec", reject_exec)
    row._open_status_colors()
    assert row._status_colors == {"1": "#aabbcc"}

    monkeypatch.setattr(
        host,
        "status_catalog",
        lambda _mid: ([SourceStatusOption("10", "НАЗНАЧЕНО", False)], None),
    )

    def accept_exec(self):
        ids = [editor.status_id for editor in self._editors]
        assert ids == ["10", "1"]
        assert self._editors[0].label_text == "НАЗНАЧЕНО"
        assert self._editors[1].label_text == "Старое"
        self._editors[0]._color = "#abcdef"
        self._editors[0]._sync_swatch()
        return SourceStatusColorsDialog.DialogCode.Accepted

    monkeypatch.setattr(SourceStatusColorsDialog, "exec", accept_exec)
    row._open_status_colors()
    assert row._status_colors["10"] == "#abcdef"
    assert row._status_colors["1"] == "#aabbcc"
    assert row._status_labels["10"] == "НАЗНАЧЕНО"
    widget._rows.remove(blank)
    widget.apply_status_highlights(settings)
    assert settings.source_status_highlights["m"].enabled is True
    assert settings.source_status_highlights["m"].colors["10"] == "#abcdef"
    assert settings.source_status_highlights["gone"].colors["9"] == "#010203"

    widget._rows.remove(row)
    widget.apply_status_highlights(settings)
    assert settings.source_status_highlights["m"].colors["1"] == "#aabbcc"
    assert "gone" in settings.source_status_highlights

    dialog = SourceModulesSettingsDialog(settings, store, host)
    qtbot.addWidget(dialog)
    card = dialog._modules_widget._rows[0]
    card.highlight_cb.setChecked(False)
    card._status_colors = {"10": "#ff00aa"}
    card._status_labels = {"10": "НАЗНАЧЕНО"}
    dialog._save()
    loaded = SettingsStore(store.path).load()
    assert loaded.source_status_highlights["m"].enabled is False
    assert loaded.source_status_highlights["m"].colors["10"] == "#ff00aa"
    assert loaded.source_status_highlights["m"].labels["10"] == "НАЗНАЧЕНО"
    assert loaded.source_status_highlights["gone"].colors["9"] == "#010203"
    assert (
        source_status_mark_color(loaded.source_status_highlights, "m", "10") is None
    )
    repo.close()


def test_workflow_status_colors_dialog_reset_pick_and_save(app_env, qtbot, monkeypatch):
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QColorDialog

    from taskmanager.domain import WORKFLOW_STATUS_LABELS
    from taskmanager.ui.settings_dialog import SettingsDialog, WorkflowStatusColorsDialog

    window, _service = app_env
    window.settings.workflow_status_colors = {"new": "#ff0000", "done": "#00ff00"}
    dialog = SettingsDialog(window.settings, window.settings_store, window)
    qtbot.addWidget(dialog)
    assert dialog.highlight_workflow_cb.text() == "Подсвечивать статусы работы"
    assert not dialog.highlight_workflow_cb.isChecked()
    assert dialog.workflow_status_colors_btn.text() == "Цвета статусов работы…"

    colors = WorkflowStatusColorsDialog(dialog._workflow_status_colors)
    qtbot.addWidget(colors)
    assert colors.windowTitle() == "Цвета статусов работы"
    assert [editor.label_text for editor in colors._editors] == list(
        WORKFLOW_STATUS_LABELS.values()
    )
    assert [editor.status_id for editor in colors._editors] == [
        status.value for status in WORKFLOW_STATUS_LABELS
    ]
    assert colors._editors[0].color == "#ff0000"
    colors._editors[0].reset_btn.click()
    assert colors._editors[0].color == ""
    assert "new" not in colors.collect()
    assert colors.collect()["done"] == "#00ff00"

    monkeypatch.setattr(QColorDialog, "getColor", lambda *_a, **_k: QColor("#112233"))
    colors._editors[1].swatch.click()
    assert colors._editors[1].color == "#112233"
    assert colors._editors[1]._picker_title == "Цвет статуса работы"

    def reject_exec(self):
        self._editors[2]._color = "#abcdef"
        return WorkflowStatusColorsDialog.DialogCode.Rejected

    monkeypatch.setattr(WorkflowStatusColorsDialog, "exec", reject_exec)
    dialog._open_workflow_status_colors()
    assert dialog._workflow_status_colors == {"new": "#ff0000", "done": "#00ff00"}

    def accept_exec(self):
        assert [editor.status_id for editor in self._editors] == [
            status.value for status in WORKFLOW_STATUS_LABELS
        ]
        self._editors[0]._color = ""
        self._editors[1]._color = "#112233"
        self._editors[1]._sync_swatch()
        return WorkflowStatusColorsDialog.DialogCode.Accepted

    monkeypatch.setattr(WorkflowStatusColorsDialog, "exec", accept_exec)
    dialog.highlight_workflow_cb.setChecked(True)
    dialog._open_workflow_status_colors()
    assert dialog._workflow_status_colors["in_progress"] == "#112233"
    assert "new" not in dialog._workflow_status_colors
    dialog._save()
    loaded = window.settings_store.load()
    assert loaded.highlight_workflow_statuses is True
    assert loaded.workflow_status_colors["in_progress"] == "#112233"
    assert loaded.workflow_status_colors["done"] == "#00ff00"
    assert "new" not in loaded.workflow_status_colors
    assert window.settings.highlight_workflow_statuses is True
