from datetime import date, datetime
from pathlib import Path

import pytest

from taskmanager.domain import Task, TaskStatus
from taskmanager.infrastructure.filesystem import TaskFilesystem
from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.services.settings_service import Settings
from taskmanager.services.task_service import (
    CreateTaskRequest,
    ServiceError,
    TaskService,
    UpdateTaskRequest,
)


@pytest.fixture
def service(tmp_path: Path):
    work = tmp_path / "work"
    work.mkdir()
    settings = Settings(
        work_dir=str(work),
        template_name=".template",
        archive_name=".archive",
    )
    repo = SqliteRepository(tmp_path / "test.db")
    svc = TaskService(repo, settings, TaskFilesystem(settings))
    yield svc
    repo.close()


def test_project_and_task_crud(service: TaskService, tmp_path: Path):
    project = service.create_project("Alpha")
    # Project folder is lazy — not created until foldered task
    assert not (tmp_path / "work" / "Alpha").is_dir()

    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="42",
            description="hello",
            date_end=date(2030, 1, 1),
            links=[("docs", "https://example.com")],
        )
    )
    folder = tmp_path / "work" / "Alpha" / task.folder_name
    assert folder.is_dir()
    assert task.folder_name == "42"
    assert task.has_folder is True
    assert task.color is None

    loaded = service.get_task(task.id)
    assert loaded.number == "42"
    assert len(loaded.links) == 1
    assert loaded.links[0].target == "https://example.com"

    updated = service.update_task(
        task.id,
        UpdateTaskRequest(description="changed", number="42"),
    )
    assert updated.folder_name == "42"
    assert folder.is_dir()
    assert updated.description == "changed"


def test_create_without_folder(service: TaskService, tmp_path: Path):
    project = service.create_project("NoFolder")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="1",
            description="db only",
            create_folder=False,
        )
    )
    assert task.has_folder is False
    assert not (tmp_path / "work" / "NoFolder" / "1").exists()

    path = service.open_task_folder(task.id)
    assert path.is_dir()
    reloaded = service.get_task(task.id)
    assert reloaded.has_folder is True


def test_rename_number_renames_folder(service: TaskService, tmp_path: Path):
    project = service.create_project("RenameDir")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="10",
            description="meta only",
        )
    )
    old_path = tmp_path / "work" / "RenameDir" / "10"
    assert old_path.is_dir()

    updated = service.update_task(task.id, UpdateTaskRequest(number="20"))
    assert updated.number == "20"
    assert updated.folder_name == "20"
    assert not old_path.exists()
    assert (tmp_path / "work" / "RenameDir" / "20").is_dir()


def test_rename_number_without_folder(service: TaskService, tmp_path: Path):
    project = service.create_project("RenameDb")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="10",
            create_folder=False,
        )
    )
    updated = service.update_task(task.id, UpdateTaskRequest(number="20"))
    assert updated.folder_name == "20"
    assert not (tmp_path / "work" / "RenameDb" / "20").exists()


def test_rename_number_rejects_duplicate(service: TaskService):
    project = service.create_project("DupNum")
    service.create_task(
        CreateTaskRequest(project_id=project.id, number="1", description="a")
    )
    other = service.create_task(
        CreateTaskRequest(project_id=project.id, number="2", description="b")
    )
    with pytest.raises(ServiceError, match="уже существует"):
        service.update_task(other.id, UpdateTaskRequest(number="1"))


def test_create_from_template(service: TaskService, tmp_path: Path):
    project = service.create_project("Beta")
    template = tmp_path / "work" / "Beta" / ".template"
    template.mkdir(parents=True)
    (template / "readme.txt").write_text("seed", encoding="utf-8")

    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="7",
            description="from tpl",
            by_template=True,
        )
    )
    assert (tmp_path / "work" / "Beta" / task.folder_name / "readme.txt").is_file()


def test_create_with_notes_file(service: TaskService, tmp_path: Path):
    project = service.create_project("NotesDir")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="55",
            description="with notes",
            create_notes_file=True,
        )
    )
    notes = tmp_path / "work" / "NotesDir" / "55" / "Notes.txt"
    assert notes.is_file()
    text = notes.read_text(encoding="utf-8")
    assert "ЗАМЕТКИ" in text
    assert len(task.links) == 1
    assert task.links[0].name == "Заметки"
    assert Path(task.links[0].target) == notes.resolve()


def test_create_notes_skips_overwrite_keeps_link(service: TaskService, tmp_path: Path):
    project = service.create_project("TplNotes")
    template = tmp_path / "work" / "TplNotes" / ".template"
    template.mkdir(parents=True)
    existing = template / "Notes.txt"
    existing.write_text("keep me", encoding="utf-8")

    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="8",
            description="tpl notes",
            by_template=True,
            create_notes_file=True,
        )
    )
    notes = tmp_path / "work" / "TplNotes" / "8" / "Notes.txt"
    assert notes.read_text(encoding="utf-8") == "keep me"
    notes_links = [link for link in task.links if link.name == "Заметки"]
    assert len(notes_links) == 1
    assert Path(notes_links[0].target).resolve() == notes.resolve()


def test_archive_moves_folder(service: TaskService, tmp_path: Path):
    project = service.create_project("Gamma")
    task = service.create_task(
        CreateTaskRequest(project_id=project.id, number="9", description="arch")
    )
    active_path = tmp_path / "work" / "Gamma" / task.folder_name
    assert active_path.is_dir()

    archived = service.archive_task(task.id)
    assert archived.is_archived
    assert archived.archive_month is not None
    assert not active_path.exists()
    assert archived.archive_project_folder == "Gamma"
    arch_path = (
        tmp_path
        / "work"
        / ".archive"
        / archived.archive_month
        / archived.archive_project_folder
        / archived.folder_name
    )
    assert arch_path.is_dir()
    assert service.list_tasks(project.id) == []


def test_archive_without_folder_db_only(service: TaskService, tmp_path: Path):
    project = service.create_project("DbArch")
    task = service.create_task(
        CreateTaskRequest(project_id=project.id, number="3", create_folder=False)
    )
    archived = service.archive_task(task.id)
    assert archived.status == TaskStatus.ARCHIVED
    assert archived.archive_month is not None
    restored = service.restore_task(task.id)
    assert restored.status == TaskStatus.ACTIVE
    assert restored.archive_month is None


def test_restore_moves_folder_back(service: TaskService, tmp_path: Path):
    project = service.create_project("RestoreMe")
    task = service.create_task(
        CreateTaskRequest(project_id=project.id, number="11", description="x")
    )
    archived = service.archive_task(task.id)
    month = archived.archive_month
    project_folder = archived.archive_project_folder
    assert project_folder == "RestoreMe"
    arch_path = tmp_path / "work" / ".archive" / month / project_folder / "11"
    assert arch_path.is_dir()

    restored = service.restore_task(task.id)
    assert restored.status == TaskStatus.ACTIVE
    assert restored.archive_project_folder is None
    assert (tmp_path / "work" / "RestoreMe" / "11").is_dir()
    assert not arch_path.exists()


def test_search(service: TaskService):
    d = service.create_project("SearchDir")
    service.create_task(
        CreateTaskRequest(project_id=d.id, number="100", description="alpha beta")
    )
    service.create_task(
        CreateTaskRequest(project_id=d.id, number="200", description="other")
    )
    found = service.search("alpha")
    assert len(found) == 1
    assert found[0].number == "100"
    by_number = service.search("200")
    assert len(by_number) == 1


def test_duplicate_project_rejected(service: TaskService):
    service.create_project("Dup")
    with pytest.raises(ServiceError):
        service.create_project("Dup")


def test_comment_and_color_null(service: TaskService):
    project = service.create_project("Meta")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="1",
            description="<b>hi</b>",
            comment="<i>note</i>",
            color=None,
            create_folder=False,
        )
    )
    assert task.comment == "<i>note</i>"
    assert task.color is None
    updated = service.update_task(
        task.id, UpdateTaskRequest(color="#ffffff", comment="plain")
    )
    assert updated.color == "#ffffff"
    cleared = service.update_task(task.id, UpdateTaskRequest(clear_color=True))
    assert cleared.color is None


def test_migration_has_folder_and_null_white(tmp_path: Path):
    db = tmp_path / "legacy.db"
    import sqlite3

    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE directories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            sort_order INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            directory_id INTEGER NOT NULL REFERENCES directories(id) ON DELETE CASCADE,
            number TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            date_end TEXT,
            color TEXT NOT NULL DEFAULT '#ffffff',
            priority INTEGER NOT NULL DEFAULT 10,
            hidden INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            folder_name TEXT NOT NULL,
            archive_month TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(directory_id, number)
        );
        INSERT INTO directories (name, sort_order) VALUES ('P', 0);
        INSERT INTO tasks (
            directory_id, number, description, color, folder_name, created_at
        ) VALUES (1, '1', 'x', '#ffffff', '1', '2026-01-01T00:00:00');
        """
    )
    conn.commit()
    conn.close()

    repo = SqliteRepository(db)
    task = repo.get_task(1)
    assert task is not None
    assert task.has_folder is True
    assert task.color is None
    assert task.comment == ""
    repo.close()


def test_reorder_projects_persists_sort_order(service: TaskService):
    a = service.create_project("Alpha")
    b = service.create_project("Beta")
    c = service.create_project("Gamma")
    service.reorder_projects([c.id, a.id, b.id])
    names = [p.name for p in service.list_projects()]
    assert names == ["Gamma", "Alpha", "Beta"]


def test_archive_migration_moves_legacy_path(tmp_path: Path):
    """Legacy ``{month}/{folder}`` moves to ``{month}/{project}/{folder}`` on service init."""
    work = tmp_path / "work"
    work.mkdir()
    settings = Settings(
        work_dir=str(work),
        template_name="_template",
        archive_name=".archive",
    )
    repo = SqliteRepository(tmp_path / "mig.db")
    project = repo.add_project("LegacyProj")
    task = Task(
        id=None,
        project_id=project.id,
        number="42",
        description="",
        folder_name="42",
        status=TaskStatus.ARCHIVED,
        archive_month="2026_08",
        archive_project_folder=None,
        has_folder=True,
        created_at=datetime(2026, 8, 1),
    )
    task = repo.add_task(task)
    legacy = work / ".archive" / "2026_08" / "42"
    legacy.mkdir(parents=True)
    (legacy / "marker.txt").write_text("x", encoding="utf-8")

    service = TaskService(repo, settings, TaskFilesystem(settings))
    refreshed = service.get_task(task.id)
    assert refreshed.archive_project_folder == "LegacyProj"
    new_path = work / ".archive" / "2026_08" / "LegacyProj" / "42"
    assert new_path.is_dir()
    assert (new_path / "marker.txt").read_text(encoding="utf-8") == "x"
    assert not legacy.exists()
    repo.close()


def test_restore_falls_back_to_legacy_archive_path(tmp_path: Path):
    work = tmp_path / "work"
    work.mkdir()
    settings = Settings(
        work_dir=str(work),
        template_name="_template",
        archive_name=".archive",
    )
    repo = SqliteRepository(tmp_path / "fb.db")
    fs = TaskFilesystem(settings)
    service = TaskService(repo, settings, fs)
    project = service.create_project("FbProj")
    task = service.create_task(
        CreateTaskRequest(project_id=project.id, number="7", description="x")
    )
    archived = service.archive_task(task.id)
    # Simulate unfinished migration: folder still at legacy path
    new_path = (
        work
        / ".archive"
        / archived.archive_month
        / archived.archive_project_folder
        / "7"
    )
    legacy = work / ".archive" / archived.archive_month / "7"
    new_path.rename(legacy)
    assert legacy.is_dir()
    assert not new_path.exists()

    restored = service.restore_task(task.id)
    assert restored.status == TaskStatus.ACTIVE
    assert (work / "FbProj" / "7").is_dir()
    assert not legacy.exists()
    repo.close()
