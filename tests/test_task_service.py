from datetime import date
from pathlib import Path

import pytest

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


def test_directory_and_task_crud(service: TaskService, tmp_path: Path):
    directory = service.create_directory("Alpha")
    assert (tmp_path / "work" / "Alpha").is_dir()

    task = service.create_task(
        CreateTaskRequest(
            directory_id=directory.id,
            number="42",
            description="hello",
            date_end=date(2030, 1, 1),
            links=[("docs", "https://example.com")],
        )
    )
    folder = tmp_path / "work" / "Alpha" / task.folder_name
    assert folder.is_dir()
    assert task.folder_name == "42"

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


def test_rename_number_renames_folder(service: TaskService, tmp_path: Path):
    directory = service.create_directory("RenameDir")
    task = service.create_task(
        CreateTaskRequest(
            directory_id=directory.id,
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


def test_rename_number_rejects_duplicate(service: TaskService):
    directory = service.create_directory("DupNum")
    service.create_task(
        CreateTaskRequest(directory_id=directory.id, number="1", description="a")
    )
    other = service.create_task(
        CreateTaskRequest(directory_id=directory.id, number="2", description="b")
    )
    with pytest.raises(ServiceError, match="уже существует"):
        service.update_task(other.id, UpdateTaskRequest(number="1"))


def test_create_from_template(service: TaskService, tmp_path: Path):
    directory = service.create_directory("Beta")
    template = tmp_path / "work" / "Beta" / ".template"
    template.mkdir()
    (template / "readme.txt").write_text("seed", encoding="utf-8")

    task = service.create_task(
        CreateTaskRequest(
            directory_id=directory.id,
            number="7",
            description="from tpl",
            by_template=True,
        )
    )
    assert (tmp_path / "work" / "Beta" / task.folder_name / "readme.txt").is_file()


def test_create_with_notes_file(service: TaskService, tmp_path: Path):
    directory = service.create_directory("NotesDir")
    task = service.create_task(
        CreateTaskRequest(
            directory_id=directory.id,
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
    directory = service.create_directory("TplNotes")
    template = tmp_path / "work" / "TplNotes" / ".template"
    template.mkdir()
    existing = template / "Notes.txt"
    existing.write_text("keep me", encoding="utf-8")

    task = service.create_task(
        CreateTaskRequest(
            directory_id=directory.id,
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
    directory = service.create_directory("Gamma")
    task = service.create_task(
        CreateTaskRequest(directory_id=directory.id, number="9", description="arch")
    )
    active_path = tmp_path / "work" / "Gamma" / task.folder_name
    assert active_path.is_dir()

    archived = service.archive_task(task.id)
    assert archived.is_archived
    assert archived.archive_month is not None
    assert not active_path.exists()
    arch_path = (
        tmp_path / "work" / ".archive" / archived.archive_month / archived.folder_name
    )
    assert arch_path.is_dir()
    assert service.list_tasks(directory.id) == []


def test_search(service: TaskService):
    d = service.create_directory("SearchDir")
    service.create_task(
        CreateTaskRequest(directory_id=d.id, number="100", description="alpha beta")
    )
    service.create_task(
        CreateTaskRequest(directory_id=d.id, number="200", description="other")
    )
    found = service.search("alpha")
    assert len(found) == 1
    assert found[0].number == "100"
    by_number = service.search("200")
    assert len(by_number) == 1


def test_duplicate_directory_rejected(service: TaskService):
    service.create_directory("Dup")
    with pytest.raises(ServiceError):
        service.create_directory("Dup")
