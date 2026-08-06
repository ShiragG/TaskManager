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
