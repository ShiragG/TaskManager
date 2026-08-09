from pathlib import Path

import pytest

from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.services.settings_service import Settings, SettingsStore
from taskmanager.services.task_service import CreateTaskRequest, TaskService
from taskmanager.ui.main_window import MainWindow


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
