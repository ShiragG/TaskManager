from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from taskmanager.domain import Link, Project, Task, TaskStatus

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
            row[1]: row
            for row in self._conn.execute("PRAGMA table_info(tasks)").fetchall()
        }
        col_names = set(cols)

        if "priority" not in col_names:
            self._conn.execute(
                "ALTER TABLE tasks ADD COLUMN priority INTEGER NOT NULL DEFAULT 10"
            )
            cols = {
                row[1]: row
                for row in self._conn.execute("PRAGMA table_info(tasks)").fetchall()
            }
            col_names = set(cols)

        if "comment" not in col_names:
            self._conn.execute(
                "ALTER TABLE tasks ADD COLUMN comment TEXT NOT NULL DEFAULT ''"
            )

        if "has_folder" not in col_names:
            self._conn.execute(
                "ALTER TABLE tasks ADD COLUMN has_folder INTEGER NOT NULL DEFAULT 1"
            )
            self._conn.execute("UPDATE tasks SET has_folder = 1")

        if "archive_project_folder" not in col_names:
            self._conn.execute(
                "ALTER TABLE tasks ADD COLUMN archive_project_folder TEXT"
            )

        # Refresh column info after possible ALTER
        cols = {
            row[1]: row
            for row in self._conn.execute("PRAGMA table_info(tasks)").fetchall()
        }
        color_info = cols.get("color")
        # row: cid, name, type, notnull, dflt_value, pk
        color_notnull = bool(color_info[3]) if color_info is not None else False
        if color_notnull:
            self._rebuild_tasks_for_nullable_color()
        else:
            self._conn.execute(
                "UPDATE tasks SET color = NULL "
                "WHERE color IS NOT NULL AND lower(color) IN ('#ffffff', '#fff', 'ffffff')"
            )

    def _rebuild_tasks_for_nullable_color(self) -> None:
        """Recreate tasks so ``color`` is nullable; migrate ``#ffffff`` → NULL."""
        self._conn.executescript(
            """
            CREATE TABLE tasks_new (
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
            INSERT INTO tasks_new (
                id, directory_id, number, description, comment, date_end, color,
                priority, hidden, has_folder, status, folder_name, archive_month,
                archive_project_folder, created_at
            )
            SELECT
                id, directory_id, number, description,
                COALESCE(comment, ''),
                date_end,
                CASE
                    WHEN color IS NOT NULL AND lower(color) IN ('#ffffff', '#fff', 'ffffff')
                    THEN NULL
                    ELSE color
                END,
                COALESCE(priority, 10),
                hidden,
                COALESCE(has_folder, 1),
                status, folder_name, archive_month,
                archive_project_folder, created_at
            FROM tasks;
            DROP TABLE tasks;
            ALTER TABLE tasks_new RENAME TO tasks;
            CREATE INDEX IF NOT EXISTS idx_tasks_directory ON tasks(directory_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
            """
        )

    # --- projects (stored as directories table) ---

    def list_projects(self) -> list[Project]:
        rows = self._conn.execute(
            "SELECT id, name, sort_order FROM directories ORDER BY sort_order, name"
        ).fetchall()
        return [Project(id=r["id"], name=r["name"], sort_order=r["sort_order"]) for r in rows]

    def get_project(self, project_id: int) -> Project | None:
        row = self._conn.execute(
            "SELECT id, name, sort_order FROM directories WHERE id = ?",
            (project_id,),
        ).fetchone()
        if row is None:
            return None
        return Project(id=row["id"], name=row["name"], sort_order=row["sort_order"])

    def get_project_by_name(self, name: str) -> Project | None:
        row = self._conn.execute(
            "SELECT id, name, sort_order FROM directories WHERE name = ?",
            (name,),
        ).fetchone()
        if row is None:
            return None
        return Project(id=row["id"], name=row["name"], sort_order=row["sort_order"])

    def add_project(self, name: str, sort_order: int | None = None) -> Project:
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
        return Project(id=cur.lastrowid, name=name, sort_order=sort_order)

    def rename_project(self, project_id: int, name: str) -> None:
        self._conn.execute(
            "UPDATE directories SET name = ? WHERE id = ?",
            (name, project_id),
        )
        self._conn.commit()

    def delete_project(self, project_id: int) -> None:
        self._conn.execute("DELETE FROM directories WHERE id = ?", (project_id,))
        self._conn.commit()

    def reorder_projects(self, project_ids: list[int]) -> None:
        """Persist tab order as ``sort_order`` (0-based index in ``project_ids``)."""
        for order, project_id in enumerate(project_ids):
            self._conn.execute(
                "UPDATE directories SET sort_order = ? WHERE id = ?",
                (order, project_id),
            )
        self._conn.commit()

    # --- tasks ---

    def list_tasks(
        self,
        project_id: int | None = None,
        *,
        status: TaskStatus | None = TaskStatus.ACTIVE,
        only_hidden: bool | None = None,
        query: str | None = None,
    ) -> list[Task]:
        clauses: list[str] = []
        params: list[object] = []
        if project_id is not None:
            clauses.append("directory_id = ?")
            params.append(project_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)
        if only_hidden is True:
            clauses.append("hidden = 1")
        elif only_hidden is False:
            clauses.append("hidden = 0")
        if query:
            like = f"%{query}%"
            clauses.append(
                "(number LIKE ? OR description LIKE ? OR comment LIKE ?)"
            )
            params.extend([like, like, like])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM tasks {where} ORDER BY number",
            params,
        ).fetchall()
        return [self._task_from_row(r) for r in rows]

    def find_task_by_number(
        self, project_id: int, number: str
    ) -> Task | None:
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE directory_id = ? AND number = ?",
            (project_id, number),
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
                directory_id, number, description, comment, date_end, color, priority,
                hidden, has_folder, status, folder_name, archive_month,
                archive_project_folder, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.project_id,
                task.number,
                task.description,
                task.comment,
                task.date_end.isoformat() if task.date_end else None,
                task.color,
                task.priority,
                1 if task.hidden else 0,
                1 if task.has_folder else 0,
                task.status.value,
                task.folder_name,
                task.archive_month,
                task.archive_project_folder,
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
                directory_id = ?, number = ?, description = ?, comment = ?,
                date_end = ?, color = ?, priority = ?, hidden = ?, has_folder = ?,
                status = ?, folder_name = ?, archive_month = ?,
                archive_project_folder = ?
            WHERE id = ?
            """,
            (
                task.project_id,
                task.number,
                task.description,
                task.comment,
                task.date_end.isoformat() if task.date_end else None,
                task.color,
                task.priority,
                1 if task.hidden else 0,
                1 if task.has_folder else 0,
                task.status.value,
                task.folder_name,
                task.archive_month,
                task.archive_project_folder,
                task.id,
            ),
        )
        self._conn.commit()

    def delete_task(self, task_id: int) -> None:
        self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self._conn.commit()

    def search_tasks(self, query: str, *, status: TaskStatus | None = TaskStatus.ACTIVE) -> list[Task]:
        return self.list_tasks(project_id=None, status=status, query=query)

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
        comment = row["comment"] if "comment" in keys and row["comment"] is not None else ""
        has_folder = bool(row["has_folder"]) if "has_folder" in keys else True
        archive_project_folder = (
            row["archive_project_folder"]
            if "archive_project_folder" in keys
            else None
        )
        color = row["color"]
        return Task(
            id=row["id"],
            project_id=row["directory_id"],
            number=row["number"],
            description=row["description"] or "",
            folder_name=row["folder_name"],
            status=TaskStatus(row["status"]),
            date_end=date_end,
            color=color,
            comment=comment,
            priority=priority,
            hidden=bool(row["hidden"]),
            has_folder=has_folder,
            archive_month=row["archive_month"],
            archive_project_folder=archive_project_folder,
            created_at=created_at,
        )
