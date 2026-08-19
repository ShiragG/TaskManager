from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime, time
from pathlib import Path

from taskmanager.domain import (
    Link,
    Project,
    ReminderRule,
    ReminderSeries,
    Task,
    TaskStatus,
    WorkflowStatus,
    html_to_plain,
    parse_reminder_rule,
    parse_whole_number,
    parse_workflow_status,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS directories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    number_high_water INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    directory_id INTEGER NOT NULL REFERENCES directories(id) ON DELETE CASCADE,
    number TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    comment TEXT NOT NULL DEFAULT '',
    description_plain TEXT NOT NULL DEFAULT '',
    comment_plain TEXT NOT NULL DEFAULT '',
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
    source_module_id TEXT,
    external_id TEXT,
    source_label TEXT,
    workflow_status TEXT NOT NULL DEFAULT 'new',
    source_status_id TEXT,
    source_status_label TEXT,
    UNIQUE(directory_id, number)
);

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    target TEXT NOT NULL,
    UNIQUE(task_id, name)
);

CREATE TABLE IF NOT EXISTS source_credentials (
    module_id TEXT PRIMARY KEY,
    login TEXT NOT NULL,
    password_ciphertext TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_modules (
    module_id TEXT PRIMARY KEY,
    github_repo TEXT NOT NULL DEFAULT '',
    display_name TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 0,
    installed_version TEXT NOT NULL DEFAULT '',
    update_asset_name TEXT NOT NULL DEFAULT '',
    update_asset_pattern TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
    text TEXT NOT NULL DEFAULT '',
    time_of_day TEXT NOT NULL,
    rule TEXT NOT NULL,
    once_date TEXT,
    weekdays TEXT NOT NULL DEFAULT '[]',
    month_day INTEGER,
    last_acknowledged_occurrence TEXT,
    skipped_occurrences TEXT NOT NULL DEFAULT '[]',
    color TEXT,
    sound_path TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_directory ON tasks(directory_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_links_task ON links(task_id);
CREATE INDEX IF NOT EXISTS idx_reminders_task ON reminders(task_id);
-- Unique source link index: see SOURCE_LINK_UNIQUE_INDEX (applied in _migrate).
"""

def _parse_time_of_day(value: str) -> time:
    text = (value or "00:00").strip()
    parts = text.split(":")
    hour = int(parts[0]) if parts and parts[0].isdigit() else 0
    minute = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    return time(hour=min(hour, 23), minute=min(minute, 59))


# Applied in _migrate after source columns exist and duplicates are renamed.
SOURCE_LINK_UNIQUE_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_source_link
ON tasks(directory_id, source_module_id, external_id)
WHERE source_module_id IS NOT NULL AND external_id IS NOT NULL;
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

        # Provenance columns after color rebuild so they are not dropped
        cols = {
            row[1]: row
            for row in self._conn.execute("PRAGMA table_info(tasks)").fetchall()
        }
        col_names = set(cols)
        if "source_module_id" not in col_names:
            self._conn.execute("ALTER TABLE tasks ADD COLUMN source_module_id TEXT")
        if "external_id" not in col_names:
            self._conn.execute("ALTER TABLE tasks ADD COLUMN external_id TEXT")
        if "source_label" not in col_names:
            self._conn.execute("ALTER TABLE tasks ADD COLUMN source_label TEXT")
        if "workflow_status" not in col_names:
            self._conn.execute(
                "ALTER TABLE tasks ADD COLUMN workflow_status TEXT NOT NULL DEFAULT 'new'"
            )
        if "source_status_id" not in col_names:
            self._conn.execute("ALTER TABLE tasks ADD COLUMN source_status_id TEXT")
        if "source_status_label" not in col_names:
            self._conn.execute(
                "ALTER TABLE tasks ADD COLUMN source_status_label TEXT"
            )

        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS source_credentials (
                module_id TEXT PRIMARY KEY,
                login TEXT NOT NULL,
                password_ciphertext TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS source_modules (
                module_id TEXT PRIMARY KEY,
                github_repo TEXT NOT NULL DEFAULT '',
                display_name TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 0,
                installed_version TEXT NOT NULL DEFAULT '',
                update_asset_name TEXT NOT NULL DEFAULT '',
                update_asset_pattern TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._dedupe_source_links()
        self._conn.executescript(SOURCE_LINK_UNIQUE_INDEX)

        self._migrate_plain_columns()
        self._migrate_number_high_water()
        self._migrate_reminders_table()
        self._migrate_reminders_task_id_nullable()
        self._migrate_reminders_color()
        self._migrate_reminders_sound_path()

    def _migrate_plain_columns(self) -> None:
        cols = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(tasks)").fetchall()
        }
        added = False
        if "description_plain" not in cols:
            self._conn.execute(
                "ALTER TABLE tasks ADD COLUMN description_plain TEXT NOT NULL DEFAULT ''"
            )
            added = True
        if "comment_plain" not in cols:
            self._conn.execute(
                "ALTER TABLE tasks ADD COLUMN comment_plain TEXT NOT NULL DEFAULT ''"
            )
            added = True
        if not added:
            empty = self._conn.execute(
                """
                SELECT COUNT(*) AS n FROM tasks
                WHERE (description != '' AND description_plain = '')
                   OR (comment != '' AND comment_plain = '')
                """
            ).fetchone()
            if empty is None or int(empty["n"]) == 0:
                return
        rows = self._conn.execute(
            "SELECT id, description, comment FROM tasks"
        ).fetchall()
        for row in rows:
            self._conn.execute(
                """
                UPDATE tasks SET description_plain = ?, comment_plain = ?
                WHERE id = ?
                """,
                (
                    html_to_plain(row["description"] or ""),
                    html_to_plain(row["comment"] or ""),
                    row["id"],
                ),
            )

    def _migrate_number_high_water(self) -> None:
        cols = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(directories)").fetchall()
        }
        if "number_high_water" in cols:
            return
        self._conn.execute(
            "ALTER TABLE directories ADD COLUMN number_high_water "
            "INTEGER NOT NULL DEFAULT 0"
        )
        projects = self._conn.execute("SELECT id FROM directories").fetchall()
        for project in projects:
            numbers = self._conn.execute(
                "SELECT number FROM tasks WHERE directory_id = ?",
                (project["id"],),
            ).fetchall()
            water = 0
            for row in numbers:
                parsed = parse_whole_number(str(row["number"]))
                if parsed is not None and parsed > water:
                    water = parsed
            self._conn.execute(
                "UPDATE directories SET number_high_water = ? WHERE id = ?",
                (water, project["id"]),
            )

    def _migrate_reminders_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
                text TEXT NOT NULL DEFAULT '',
                time_of_day TEXT NOT NULL,
                rule TEXT NOT NULL,
                once_date TEXT,
                weekdays TEXT NOT NULL DEFAULT '[]',
                month_day INTEGER,
                last_acknowledged_occurrence TEXT,
                skipped_occurrences TEXT NOT NULL DEFAULT '[]',
                color TEXT,
                sound_path TEXT
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reminders_task ON reminders(task_id)"
        )

    def _migrate_reminders_task_id_nullable(self) -> None:
        cols = {
            row["name"]: row
            for row in self._conn.execute("PRAGMA table_info(reminders)").fetchall()
        }
        task_col = cols.get("task_id")
        if task_col is None or int(task_col["notnull"]) == 0:
            return
        self._conn.executescript(
            """
            CREATE TABLE reminders_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
                text TEXT NOT NULL DEFAULT '',
                time_of_day TEXT NOT NULL,
                rule TEXT NOT NULL,
                once_date TEXT,
                weekdays TEXT NOT NULL DEFAULT '[]',
                month_day INTEGER,
                last_acknowledged_occurrence TEXT,
                skipped_occurrences TEXT NOT NULL DEFAULT '[]'
            );
            INSERT INTO reminders_new (
                id, task_id, text, time_of_day, rule, once_date, weekdays,
                month_day, last_acknowledged_occurrence, skipped_occurrences
            )
            SELECT
                id, task_id, text, time_of_day, rule, once_date, weekdays,
                month_day, last_acknowledged_occurrence, skipped_occurrences
            FROM reminders;
            DROP TABLE reminders;
            ALTER TABLE reminders_new RENAME TO reminders;
            CREATE INDEX IF NOT EXISTS idx_reminders_task ON reminders(task_id);
            """
        )

    def _migrate_reminders_color(self) -> None:
        cols = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(reminders)").fetchall()
        }
        if "color" in cols:
            return
        self._conn.execute("ALTER TABLE reminders ADD COLUMN color TEXT")

    def _migrate_reminders_sound_path(self) -> None:
        cols = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(reminders)").fetchall()
        }
        if "sound_path" in cols:
            return
        self._conn.execute("ALTER TABLE reminders ADD COLUMN sound_path TEXT")

    def _dedupe_source_links(self) -> None:
        """Rename duplicate source links so the unique index can be created.

        Canon = min(id) keeps the original external_id; others get
        ``{original}_Дубль_{8hex}`` (sha256 of task id, retry on clash).
        """
        groups = self._conn.execute(
            """
            SELECT directory_id, source_module_id, external_id, COUNT(*) AS n
            FROM tasks
            WHERE source_module_id IS NOT NULL AND external_id IS NOT NULL
            GROUP BY directory_id, source_module_id, external_id
            HAVING n > 1
            """
        ).fetchall()
        for group in groups:
            rows = self._conn.execute(
                """
                SELECT id, external_id FROM tasks
                WHERE directory_id = ?
                  AND source_module_id = ?
                  AND external_id = ?
                ORDER BY id
                """,
                (
                    group["directory_id"],
                    group["source_module_id"],
                    group["external_id"],
                ),
            ).fetchall()
            original = group["external_id"]
            for row in rows[1:]:
                self._rename_duplicate_external_id(
                    row["id"],
                    original,
                    directory_id=group["directory_id"],
                    source_module_id=group["source_module_id"],
                )

    def _rename_duplicate_external_id(
        self,
        task_id: int,
        original: str,
        *,
        directory_id: int,
        source_module_id: str,
    ) -> None:
        digest = hashlib.sha256(str(task_id).encode()).hexdigest()
        for end in range(8, len(digest) + 1):
            candidate = f"{original}_Дубль_{digest[:end]}"
            clash = self._conn.execute(
                """
                SELECT 1 FROM tasks
                WHERE directory_id = ?
                  AND source_module_id = ?
                  AND external_id = ?
                  AND id != ?
                LIMIT 1
                """,
                (directory_id, source_module_id, candidate, task_id),
            ).fetchone()
            if clash is None:
                self._conn.execute(
                    "UPDATE tasks SET external_id = ? WHERE id = ?",
                    (candidate, task_id),
                )
                return
        self._conn.execute(
            "UPDATE tasks SET external_id = ? WHERE id = ?",
            (f"{original}_Дубль_{digest}_{task_id}", task_id),
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
            "SELECT id, name, sort_order, number_high_water "
            "FROM directories ORDER BY sort_order, name"
        ).fetchall()
        return [self._project_from_row(r) for r in rows]

    def get_project(self, project_id: int) -> Project | None:
        row = self._conn.execute(
            "SELECT id, name, sort_order, number_high_water "
            "FROM directories WHERE id = ?",
            (project_id,),
        ).fetchone()
        if row is None:
            return None
        return self._project_from_row(row)

    def get_project_by_name(self, name: str) -> Project | None:
        row = self._conn.execute(
            "SELECT id, name, sort_order, number_high_water "
            "FROM directories WHERE name = ?",
            (name,),
        ).fetchone()
        if row is None:
            return None
        return self._project_from_row(row)

    def add_project(self, name: str, sort_order: int | None = None) -> Project:
        if sort_order is None:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order FROM directories"
            ).fetchone()
            sort_order = int(row["next_order"])
        cur = self._conn.execute(
            "INSERT INTO directories (name, sort_order, number_high_water) "
            "VALUES (?, ?, 0)",
            (name, sort_order),
        )
        self._conn.commit()
        return Project(
            id=cur.lastrowid, name=name, sort_order=sort_order, number_high_water=0
        )

    @staticmethod
    def _project_from_row(row: sqlite3.Row) -> Project:
        keys = row.keys()
        water = int(row["number_high_water"]) if "number_high_water" in keys else 0
        return Project(
            id=row["id"],
            name=row["name"],
            sort_order=row["sort_order"],
            number_high_water=water,
        )

    def set_number_high_water(self, project_id: int, value: int) -> None:
        self._conn.execute(
            "UPDATE directories SET number_high_water = ? WHERE id = ?",
            (int(value), project_id),
        )
        self._conn.commit()

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
                "(number LIKE ? OR description_plain LIKE ? OR comment_plain LIKE ?)"
            )
            params.extend([like, like, like])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM tasks {where} ORDER BY number",
            params,
        ).fetchall()
        return [self._task_from_row(r) for r in rows]

    def list_archive_months(self, project_id: int) -> list[str]:
        """Distinct archive_month values for archived tasks of a project."""
        rows = self._conn.execute(
            """
            SELECT DISTINCT archive_month FROM tasks
            WHERE directory_id = ?
              AND status = ?
              AND archive_month IS NOT NULL
              AND archive_month != ''
            ORDER BY archive_month DESC
            """,
            (project_id, TaskStatus.ARCHIVED.value),
        ).fetchall()
        return [str(r["archive_month"]) for r in rows]

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

    def list_source_external_ids(self, project_id: int, module_id: str) -> set[str]:
        """All external_ids linked to *module_id* in the Project (any status/hidden)."""
        rows = self._conn.execute(
            """
            SELECT external_id FROM tasks
            WHERE directory_id = ?
              AND source_module_id = ?
              AND external_id IS NOT NULL
            """,
            (project_id, module_id),
        ).fetchall()
        return {str(r["external_id"]) for r in rows}

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
                directory_id, number, description, comment,
                description_plain, comment_plain,
                date_end, color, priority,
                hidden, has_folder, status, folder_name, archive_month,
                archive_project_folder, created_at,
                source_module_id, external_id, source_label,
                workflow_status, source_status_id, source_status_label
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.project_id,
                task.number,
                task.description,
                task.comment,
                task.description_plain,
                task.comment_plain,
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
                task.source_module_id,
                task.external_id,
                task.source_label,
                task.workflow_status.value,
                task.source_status_id,
                task.source_status_label,
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
                description_plain = ?, comment_plain = ?,
                date_end = ?, color = ?, priority = ?, hidden = ?, has_folder = ?,
                status = ?, folder_name = ?, archive_month = ?,
                archive_project_folder = ?,
                source_module_id = ?, external_id = ?, source_label = ?,
                workflow_status = ?, source_status_id = ?, source_status_label = ?
            WHERE id = ?
            """,
            (
                task.project_id,
                task.number,
                task.description,
                task.comment,
                task.description_plain,
                task.comment_plain,
                task.date_end.isoformat() if task.date_end else None,
                task.color,
                task.priority,
                1 if task.hidden else 0,
                1 if task.has_folder else 0,
                task.status.value,
                task.folder_name,
                task.archive_month,
                task.archive_project_folder,
                task.source_module_id,
                task.external_id,
                task.source_label,
                task.workflow_status.value,
                task.source_status_id,
                task.source_status_label,
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
        source_module_id = (
            row["source_module_id"] if "source_module_id" in keys else None
        )
        external_id = row["external_id"] if "external_id" in keys else None
        source_label = row["source_label"] if "source_label" in keys else None
        workflow_status = (
            parse_workflow_status(row["workflow_status"])
            if "workflow_status" in keys
            else WorkflowStatus.NEW
        )
        source_status_id = (
            row["source_status_id"] if "source_status_id" in keys else None
        )
        source_status_label = (
            row["source_status_label"] if "source_status_label" in keys else None
        )
        description_plain = (
            row["description_plain"]
            if "description_plain" in keys and row["description_plain"] is not None
            else ""
        )
        comment_plain = (
            row["comment_plain"]
            if "comment_plain" in keys and row["comment_plain"] is not None
            else ""
        )
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
            source_module_id=source_module_id,
            external_id=external_id,
            source_label=source_label,
            workflow_status=workflow_status,
            source_status_id=source_status_id,
            source_status_label=source_status_label,
            description_plain=description_plain,
            comment_plain=comment_plain,
        )

    # --- source credentials ---

    def upsert_source_credentials(
        self, module_id: str, login: str, password_ciphertext: str
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO source_credentials (module_id, login, password_ciphertext)
            VALUES (?, ?, ?)
            ON CONFLICT(module_id) DO UPDATE SET
                login = excluded.login,
                password_ciphertext = excluded.password_ciphertext
            """,
            (module_id, login, password_ciphertext),
        )
        self._conn.commit()

    def get_source_credentials(self, module_id: str) -> tuple[str, str] | None:
        row = self._conn.execute(
            "SELECT login, password_ciphertext FROM source_credentials WHERE module_id = ?",
            (module_id,),
        ).fetchone()
        if row is None:
            return None
        return str(row["login"]), str(row["password_ciphertext"])

    def delete_source_credentials(self, module_id: str) -> None:
        self._conn.execute(
            "DELETE FROM source_credentials WHERE module_id = ?", (module_id,)
        )
        self._conn.commit()

    # --- source modules registry ---

    def list_source_modules(self) -> list[dict]:
        rows = self._conn.execute(
            """
            SELECT module_id, github_repo, display_name, enabled, installed_version,
                   update_asset_name, update_asset_pattern
            FROM source_modules
            ORDER BY display_name, module_id
            """
        ).fetchall()
        return [dict(r) for r in rows]

    def get_source_module(self, module_id: str) -> dict | None:
        row = self._conn.execute(
            """
            SELECT module_id, github_repo, display_name, enabled, installed_version,
                   update_asset_name, update_asset_pattern
            FROM source_modules WHERE module_id = ?
            """,
            (module_id,),
        ).fetchone()
        return dict(row) if row is not None else None

    def upsert_source_module(
        self,
        *,
        module_id: str,
        github_repo: str = "",
        display_name: str = "",
        enabled: bool = False,
        installed_version: str = "",
        update_asset_name: str = "",
        update_asset_pattern: str = "",
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO source_modules (
                module_id, github_repo, display_name, enabled, installed_version,
                update_asset_name, update_asset_pattern
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(module_id) DO UPDATE SET
                github_repo = excluded.github_repo,
                display_name = excluded.display_name,
                enabled = excluded.enabled,
                installed_version = excluded.installed_version,
                update_asset_name = excluded.update_asset_name,
                update_asset_pattern = excluded.update_asset_pattern
            """,
            (
                module_id,
                github_repo,
                display_name,
                1 if enabled else 0,
                installed_version,
                update_asset_name,
                update_asset_pattern,
            ),
        )
        self._conn.commit()

    def delete_source_module(self, module_id: str) -> None:
        self._conn.execute(
            "DELETE FROM source_modules WHERE module_id = ?", (module_id,)
        )
        self._conn.commit()

    def list_task_numbers(self, project_id: int) -> list[str]:
        rows = self._conn.execute(
            "SELECT number FROM tasks WHERE directory_id = ?",
            (project_id,),
        ).fetchall()
        return [str(r["number"]) for r in rows]

    # --- reminders ---

    def list_reminders(
        self, *, task_id: int | None = None
    ) -> list[ReminderSeries]:
        if task_id is None:
            rows = self._conn.execute(
                "SELECT * FROM reminders ORDER BY id"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM reminders WHERE task_id = ? ORDER BY id",
                (task_id,),
            ).fetchall()
        return [self._reminder_from_row(r) for r in rows]

    def get_reminder(self, reminder_id: int) -> ReminderSeries | None:
        row = self._conn.execute(
            "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
        ).fetchone()
        if row is None:
            return None
        return self._reminder_from_row(row)

    def add_reminder(self, series: ReminderSeries) -> ReminderSeries:
        cur = self._conn.execute(
            """
            INSERT INTO reminders (
                task_id, text, time_of_day, rule, once_date, weekdays,
                month_day, last_acknowledged_occurrence, skipped_occurrences,
                color, sound_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._reminder_row_values(series),
        )
        self._conn.commit()
        series.id = cur.lastrowid
        return series

    def update_reminder(self, series: ReminderSeries) -> None:
        assert series.id is not None
        values = self._reminder_row_values(series)
        self._conn.execute(
            """
            UPDATE reminders SET
                task_id = ?, text = ?, time_of_day = ?, rule = ?,
                once_date = ?, weekdays = ?, month_day = ?,
                last_acknowledged_occurrence = ?, skipped_occurrences = ?,
                color = ?, sound_path = ?
            WHERE id = ?
            """,
            (*values, series.id),
        )
        self._conn.commit()

    def delete_reminder(self, reminder_id: int) -> None:
        self._conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        self._conn.commit()

    def delete_reminders_for_task(self, task_id: int) -> None:
        self._conn.execute("DELETE FROM reminders WHERE task_id = ?", (task_id,))
        self._conn.commit()

    @staticmethod
    def _reminder_row_values(series: ReminderSeries) -> tuple[object, ...]:
        skipped = [
            occ.isoformat(timespec="seconds") for occ in series.skipped_occurrences
        ]
        acked = (
            series.last_acknowledged_occurrence.isoformat(timespec="seconds")
            if series.last_acknowledged_occurrence
            else None
        )
        return (
            series.task_id,
            series.text,
            series.time_of_day.strftime("%H:%M"),
            series.rule.value,
            series.once_date.isoformat() if series.once_date else None,
            json.dumps(list(series.weekdays)),
            series.month_day,
            acked,
            json.dumps(skipped),
            series.color or None,
            (series.sound_path.strip() if series.sound_path else None),
        )

    @staticmethod
    def _reminder_from_row(row: sqlite3.Row) -> ReminderSeries:
        clock = _parse_time_of_day(row["time_of_day"])
        once_date = date.fromisoformat(row["once_date"]) if row["once_date"] else None
        try:
            weekdays_raw = json.loads(row["weekdays"] or "[]")
        except json.JSONDecodeError:
            weekdays_raw = []
        weekdays = tuple(
            int(w) for w in weekdays_raw if isinstance(w, int) and 0 <= w <= 6
        )
        acked = (
            datetime.fromisoformat(row["last_acknowledged_occurrence"])
            if row["last_acknowledged_occurrence"]
            else None
        )
        try:
            skipped_raw = json.loads(row["skipped_occurrences"] or "[]")
        except json.JSONDecodeError:
            skipped_raw = []
        skipped: list[datetime] = []
        for item in skipped_raw:
            try:
                skipped.append(datetime.fromisoformat(str(item)))
            except ValueError:
                continue
        raw_task = row["task_id"]
        color = None
        if "color" in row.keys():
            raw_color = row["color"]
            color = str(raw_color) if raw_color else None
        sound_path = None
        if "sound_path" in row.keys():
            raw_sound = row["sound_path"]
            sound_path = str(raw_sound).strip() if raw_sound else None
            if not sound_path:
                sound_path = None
        return ReminderSeries(
            id=row["id"],
            task_id=int(raw_task) if raw_task is not None else None,
            text=row["text"] or "",
            time_of_day=clock,
            rule=parse_reminder_rule(row["rule"]),
            once_date=once_date,
            weekdays=weekdays,
            month_day=row["month_day"],
            last_acknowledged_occurrence=acked,
            skipped_occurrences=tuple(skipped),
            color=color,
            sound_path=sound_path,
        )

    def count_tasks_for_source_module(self, module_id: str) -> int:
        row = self._conn.execute(
            """
            SELECT COUNT(*) AS n FROM tasks
            WHERE source_module_id = ?
            """,
            (module_id,),
        ).fetchone()
        return int(row["n"]) if row is not None else 0

    def clear_task_source_links(self, module_id: str) -> int:
        """Clear provenance fields on Tasks linked to module_id; return affected count."""
        cur = self._conn.execute(
            """
            UPDATE tasks SET
                source_module_id = NULL,
                external_id = NULL,
                source_label = NULL
            WHERE source_module_id = ?
            """,
            (module_id,),
        )
        self._conn.commit()
        return int(cur.rowcount)
