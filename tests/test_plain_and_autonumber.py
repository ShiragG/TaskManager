from pathlib import Path

from taskmanager.infrastructure.filesystem import TaskFilesystem
from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.services.settings_service import Settings
from taskmanager.services.task_service import CreateTaskRequest, TaskService


def _service(tmp_path: Path) -> TaskService:
    work = tmp_path / "work"
    work.mkdir()
    settings = Settings(work_dir=str(work), autonumber_on_create=True)
    repo = SqliteRepository(tmp_path / "p.db")
    return TaskService(repo, settings, TaskFilesystem(settings))


def test_plain_written_on_save_and_search_uses_plain(tmp_path: Path):
    service = _service(tmp_path)
    project = service.create_project("Plain")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="1",
            description="<b>visible word</b> and more",
            comment="<i>note token</i>",
            create_folder=False,
        )
    )
    loaded = service.get_task(task.id)
    assert loaded.description_plain == "visible word and more"
    assert loaded.comment_plain == "note token"
    found = service.list_tasks(project.id, query="visible word")
    assert len(found) == 1
    found_comment = service.list_tasks(project.id, query="note token")
    assert len(found_comment) == 1
    # HTML tags are not searchable
    assert service.list_tasks(project.id, query="<b>") == []
    service.repo.close()


def test_plain_backfill_on_legacy_db(tmp_path: Path):
    import sqlite3

    db = tmp_path / "legacy-plain.db"
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
            comment TEXT NOT NULL DEFAULT '',
            date_end TEXT,
            color TEXT,
            priority INTEGER NOT NULL DEFAULT 10,
            hidden INTEGER NOT NULL DEFAULT 0,
            has_folder INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'active',
            folder_name TEXT NOT NULL,
            archive_month TEXT,
            archive_project_folder TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(directory_id, number)
        );
        INSERT INTO directories (name, sort_order) VALUES ('P', 0);
        INSERT INTO tasks (
            directory_id, number, description, comment, folder_name, created_at
        ) VALUES (1, '1', '<b>backfilled</b>', '<i>cplain</i>', '1', '2026-01-01T00:00:00');
        """
    )
    conn.commit()
    conn.close()

    repo = SqliteRepository(db)
    task = repo.get_task(1)
    assert task is not None
    assert task.description_plain == "backfilled"
    assert task.comment_plain == "cplain"
    found = repo.list_tasks(1, query="backfilled")
    assert len(found) == 1
    repo.close()


def test_autonumber_custom_keeps_proposal(tmp_path: Path):
    service = _service(tmp_path)
    project = service.create_project("Num")
    assert service.propose_next_number(project.id) == "1"
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="ABC",
            create_folder=False,
            proposed_number="1",
        )
    )
    assert service.propose_next_number(project.id) == "1"
    service.repo.close()


def test_autonumber_accept_proposed_advances(tmp_path: Path):
    service = _service(tmp_path)
    project = service.create_project("Num2")
    assert service.propose_next_number(project.id) == "1"
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="1",
            create_folder=False,
            proposed_number="1",
        )
    )
    assert service.propose_next_number(project.id) == "2"
    service.repo.close()


def test_autonumber_skips_occupied_proposal(tmp_path: Path):
    service = _service(tmp_path)
    project = service.create_project("Num3")
    service.repo.set_number_high_water(project.id, 4)
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="5",
            create_folder=False,
        )
    )
    assert service.propose_next_number(project.id) == "6"
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="6",
            create_folder=False,
            proposed_number="6",
        )
    )
    assert service.repo.get_project(project.id).number_high_water == 6
    assert service.propose_next_number(project.id) == "7"
    service.repo.close()


def test_autonumber_import_does_not_advance(tmp_path: Path):
    service = _service(tmp_path)
    project = service.create_project("Imp")
    service.create_task(
        CreateTaskRequest(
            project_id=project.id,
            number="10",
            create_folder=False,
        )
    )
    assert service.propose_next_number(project.id) == "1"
    service.repo.close()


def test_autonumber_init_from_existing_integers(tmp_path: Path):
    import sqlite3

    db = tmp_path / "legacy-num.db"
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
            comment TEXT NOT NULL DEFAULT '',
            date_end TEXT,
            color TEXT,
            priority INTEGER NOT NULL DEFAULT 10,
            hidden INTEGER NOT NULL DEFAULT 0,
            has_folder INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'active',
            folder_name TEXT NOT NULL,
            archive_month TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(directory_id, number)
        );
        INSERT INTO directories (name, sort_order) VALUES ('P', 0);
        INSERT INTO tasks (directory_id, number, description, folder_name, created_at)
        VALUES
            (1, '1', '', '1', '2026-01-01T00:00:00'),
            (1, '3', '', '3', '2026-01-01T00:00:00'),
            (1, 'ABC', '', 'ABC', '2026-01-01T00:00:00');
        """
    )
    conn.commit()
    conn.close()
    repo = SqliteRepository(db)
    project = repo.get_project(1)
    assert project is not None
    assert project.number_high_water == 3
    repo.close()
