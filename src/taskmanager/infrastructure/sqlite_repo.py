from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from taskmanager.domain import Directory, Link, Task, TaskStatus

SCHEMA = """
CREATE TABLE IF NOT EXISTS directories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tasks (
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

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    target TEXT NOT NULL,
    UNIQUE(task_id, name)
);

CREATE INDEX IF NOT EXISTS idx_tasks_directory ON tasks(directory_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_links_task ON links(task_id);
"""


class SqliteRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._migrate()
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _migrate(self) -> None:
        cols = {
            row[1] for row in self._conn.execute("PRAGMA table_info(tasks)").fetchall()
        }
        if "priority" not in cols:
            self._conn.execute(
                "ALTER TABLE tasks ADD COLUMN priority INTEGER NOT NULL DEFAULT 10"
            )

    # --- directories ---

    def list_directories(self) -> list[Directory]:
        rows = self._conn.execute(
            "SELECT id, name, sort_order FROM directories ORDER BY sort_order, name"
        ).fetchall()
        return [Directory(id=r["id"], name=r["name"], sort_order=r["sort_order"]) for r in rows]

    def get_directory(self, directory_id: int) -> Directory | None:
        row = self._conn.execute(
            "SELECT id, name, sort_order FROM directories WHERE id = ?",
            (directory_id,),
        ).fetchone()
        if row is None:
            return None
        return Directory(id=row["id"], name=row["name"], sort_order=row["sort_order"])

    def get_directory_by_name(self, name: str) -> Directory | None:
        row = self._conn.execute(
            "SELECT id, name, sort_order FROM directories WHERE name = ?",
            (name,),
        ).fetchone()
        if row is None:
            return None
        return Directory(id=row["id"], name=row["name"], sort_order=row["sort_order"])

    def add_directory(self, name: str, sort_order: int | None = None) -> Directory:
        if sort_order is None:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order FROM directories"
            ).fetchone()
            sort_order = int(row["next_order"])
        cur = self._conn.execute(
            "INSERT INTO directories (name, sort_order) VALUES (?, ?)",
            (name, sort_order),
        )
        self._conn.commit()
        return Directory(id=cur.lastrowid, name=name, sort_order=sort_order)

    def rename_directory(self, directory_id: int, name: str) -> None:
        self._conn.execute(
            "UPDATE directories SET name = ? WHERE id = ?",
            (name, directory_id),
        )
        self._conn.commit()

    def delete_directory(self, directory_id: int) -> None:
        self._conn.execute("DELETE FROM directories WHERE id = ?", (directory_id,))
        self._conn.commit()

    # --- tasks ---

    def list_tasks(
        self,
        directory_id: int | None = None,
        *,
        status: TaskStatus | None = TaskStatus.ACTIVE,
        only_hidden: bool | None = None,
        query: str | None = None,
    ) -> list[Task]:
        clauses: list[str] = []
        params: list[object] = []
        if directory_id is not None:
            clauses.append("directory_id = ?")
            params.append(directory_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)
        if only_hidden is True:
            clauses.append("hidden = 1")
        elif only_hidden is False:
            clauses.append("hidden = 0")
        if query:
            like = f"%{query}%"
            clauses.append("(number LIKE ? OR description LIKE ?)")
            params.extend([like, like])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM tasks {where} ORDER BY number",
            params,
        ).fetchall()
        return [self._task_from_row(r) for r in rows]

    def find_task_by_number(
        self, directory_id: int, number: str
    ) -> Task | None:
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE directory_id = ? AND number = ?",
            (directory_id, number),
        ).fetchone()
        if row is None:
            return None
        return self._task_from_row(row)

    def get_task(self, task_id: int) -> Task | None:
        row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        task = self._task_from_row(row)
        task.links = self.list_links(task_id)
        return task

    def add_task(self, task: Task) -> Task:
        created = task.created_at or datetime.now()
        cur = self._conn.execute(
            """
            INSERT INTO tasks (
                directory_id, number, description, date_end, color, priority,
                hidden, status, folder_name, archive_month, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.directory_id,
                task.number,
                task.description,
                task.date_end.isoformat() if task.date_end else None,
                task.color,
                task.priority,
                1 if task.hidden else 0,
                task.status.value,
                task.folder_name,
                task.archive_month,
                created.isoformat(timespec="seconds"),
            ),
        )
        self._conn.commit()
        task.id = cur.lastrowid
        task.created_at = created
        return task

    def update_task(self, task: Task) -> None:
        assert task.id is not None
        self._conn.execute(
            """
            UPDATE tasks SET
                directory_id = ?, number = ?, description = ?, date_end = ?,
                color = ?, priority = ?, hidden = ?, status = ?, folder_name = ?,
                archive_month = ?
            WHERE id = ?
            """,
            (
                task.directory_id,
                task.number,
                task.description,
                task.date_end.isoformat() if task.date_end else None,
                task.color,
                task.priority,
                1 if task.hidden else 0,
                task.status.value,
                task.folder_name,
                task.archive_month,
                task.id,
            ),
        )
        self._conn.commit()

    def delete_task(self, task_id: int) -> None:
        self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self._conn.commit()

    def search_tasks(self, query: str, *, status: TaskStatus | None = TaskStatus.ACTIVE) -> list[Task]:
        return self.list_tasks(directory_id=None, status=status, query=query)

    # --- links ---

    def list_links(self, task_id: int) -> list[Link]:
        rows = self._conn.execute(
            "SELECT id, task_id, name, target FROM links WHERE task_id = ? ORDER BY name",
            (task_id,),
        ).fetchall()
        return [
            Link(id=r["id"], task_id=r["task_id"], name=r["name"], target=r["target"])
            for r in rows
        ]

    def replace_links(self, task_id: int, links: list[Link]) -> list[Link]:
        self._conn.execute("DELETE FROM links WHERE task_id = ?", (task_id,))
        result: list[Link] = []
        for link in links:
            cur = self._conn.execute(
                "INSERT INTO links (task_id, name, target) VALUES (?, ?, ?)",
                (task_id, link.name, link.target),
            )
            result.append(
                Link(id=cur.lastrowid, task_id=task_id, name=link.name, target=link.target)
            )
        self._conn.commit()
        return result

    def _task_from_row(self, row: sqlite3.Row) -> Task:
        date_end = date.fromisoformat(row["date_end"]) if row["date_end"] else None
        created_at = (
            datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
        )
        keys = row.keys()
        priority = int(row["priority"]) if "priority" in keys else 10
        return Task(
            id=row["id"],
            directory_id=row["directory_id"],
            number=row["number"],
            description=row["description"],
            folder_name=row["folder_name"],
            status=TaskStatus(row["status"]),
            date_end=date_end,
            color=row["color"],
            priority=priority,
            hidden=bool(row["hidden"]),
            archive_month=row["archive_month"],
            created_at=created_at,
        )
