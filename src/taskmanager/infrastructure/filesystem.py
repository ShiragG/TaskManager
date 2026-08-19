from __future__ import annotations

import os
import shutil
from datetime import date
from pathlib import Path

from taskmanager.domain import Project, Task, TaskStatus
from taskmanager.infrastructure.paths import resolve_work_dir
from taskmanager.services.settings_service import Settings

NOTES_FILE_NAME = "Notes.txt"
NOTES_LINK_NAME = "Заметки"
SOURCE_FILES_DIR_NAME = "files"


def source_files_dir(task_folder: Path) -> Path:
    return task_folder / SOURCE_FILES_DIR_NAME


def existing_source_file_names(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    return [p.name for p in directory.iterdir()]


def source_files_present(directory: Path | None) -> bool:
    """True if the dedicated Source files folder exists and has a non-dot entry."""
    if directory is None or not directory.is_dir():
        return False
    return any(not p.name.startswith(".") for p in directory.iterdir())


class FilesystemError(Exception):
    """Filesystem operation failed."""


def notes_file_content(today: date | None = None) -> str:
    """Header written into a new Notes.txt (date as DD.MM.YY)."""
    d = today or date.today()
    stamp = d.strftime("%d.%m.%y")
    return (
        "-------------------------\n"
        "---------ЗАМЕТКИ---------\n"
        f"---------{stamp}--------\n"
        "-------------------------\n"
    )


class TaskFilesystem:
    """Resolve and mutate task/project folders on disk."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def work_dir(self) -> Path:
        return resolve_work_dir(self.settings.work_dir)

    def project_path(self, project: Project) -> Path:
        return self.work_dir / project.name

    def template_path(self, project: Project) -> Path:
        return self.project_path(project) / self.settings.template_name

    def archive_root(self) -> Path:
        return self.work_dir / self.settings.archive_name

    def archived_task_path(self, task: Task) -> Path:
        """Preferred archive layout: ``{month}/{archive_project_folder}/{folder_name}``."""
        if not task.archive_month:
            raise FilesystemError(
                f"У архивной заявки {task.number} не указан месяц архива"
            )
        if not task.archive_project_folder:
            raise FilesystemError(
                f"У архивной заявки {task.number} не указана папка проекта в архиве"
            )
        return (
            self.archive_root()
            / task.archive_month
            / task.archive_project_folder
            / task.folder_name
        )

    def legacy_archived_task_path(self, task: Task) -> Path:
        """Pre-0.6.2 layout: ``{month}/{folder_name}``."""
        if not task.archive_month:
            raise FilesystemError(
                f"У архивной заявки {task.number} не указан месяц архива"
            )
        return self.archive_root() / task.archive_month / task.folder_name

    def resolve_archived_task_path(self, task: Task) -> Path:
        """New path if present; otherwise legacy path when the folder still lives there."""
        if task.archive_project_folder:
            preferred = self.archived_task_path(task)
            if preferred.is_dir():
                return preferred
            legacy = self.legacy_archived_task_path(task)
            if legacy.is_dir():
                return legacy
            return preferred
        return self.legacy_archived_task_path(task)

    def task_path(self, project: Project, task: Task) -> Path:
        if task.status == TaskStatus.ARCHIVED:
            return self.resolve_archived_task_path(task)
        return self.project_path(project) / task.folder_name

    def ensure_project(self, project: Project) -> Path:
        path = self.project_path(project)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def rename_project(self, old: Project, new_name: str) -> Path | None:
        """Rename project folder if it exists; return new path or None if absent."""
        old_path = self.project_path(old)
        new_path = self.work_dir / new_name
        if old_path == new_path:
            return new_path if old_path.is_dir() else None
        if not old_path.is_dir():
            return None
        if new_path.exists():
            raise FilesystemError(f"Папка уже существует: {new_path}")
        old_path.rename(new_path)
        return new_path

    def validate_create_task_folder(
        self,
        project: Project,
        folder_name: str,
        *,
        by_template: bool = False,
    ) -> None:
        """Raise FilesystemError if a new task folder cannot be created."""
        dest = self.project_path(project) / folder_name
        if dest.exists():
            raise FilesystemError(f"Папка заявки уже существует: {dest}")
        if by_template:
            template = self.template_path(project)
            if not template.is_dir():
                raise FilesystemError(
                    f"Не найден шаблон «{self.settings.template_name}» "
                    f"в проекте «{project.name}»"
                )
        parent = self.project_path(project)
        if parent.exists() and not parent.is_dir():
            raise FilesystemError(f"Путь проекта занят файлом: {parent}")
        if parent.is_dir() and not os.access(parent, os.W_OK):
            raise FilesystemError(f"Нет прав на запись в проект: {parent}")

    def validate_rename_task_folder(
        self,
        project: Project,
        task: Task,
        new_folder_name: str,
    ) -> None:
        """Raise FilesystemError if the task folder cannot be renamed."""
        src = self.task_path(project, task)
        dest = self.project_path(project) / new_folder_name
        if src == dest:
            return
        if not src.is_dir():
            raise FilesystemError(f"Папка заявки не найдена: {src}")
        if dest.exists():
            raise FilesystemError(f"Папка заявки уже существует: {dest}")

    def create_task_folder(
        self,
        project: Project,
        folder_name: str,
        *,
        by_template: bool,
    ) -> Path:
        self.validate_create_task_folder(
            project, folder_name, by_template=by_template
        )
        self.ensure_project(project)
        dest = self.project_path(project) / folder_name

        if by_template:
            template = self.template_path(project)
            shutil.copytree(template, dest)
        else:
            dest.mkdir(parents=True)
        return dest

    def ensure_task_folder(self, project: Project, task: Task) -> Path:
        """Create the task folder if missing (empty, no template)."""
        self.ensure_project(project)
        path = self.task_path(project, task)
        if not path.is_dir():
            if path.exists():
                raise FilesystemError(f"Путь заявки занят файлом: {path}")
            path.mkdir(parents=True)
        return path

    def ensure_notes_file(self, task_folder: Path, *, today: date | None = None) -> Path:
        """Create Notes.txt with header if missing; never overwrite existing."""
        path = task_folder / NOTES_FILE_NAME
        if not path.exists():
            path.write_text(notes_file_content(today), encoding="utf-8")
        return path.resolve()

    def rename_task_folder(
        self,
        project: Project,
        task: Task,
        new_folder_name: str,
    ) -> Path:
        self.validate_rename_task_folder(project, task, new_folder_name)
        src = self.task_path(project, task)
        dest = self.project_path(project) / new_folder_name
        if src == dest:
            return dest
        src.rename(dest)
        return dest

    def archive_task(
        self,
        project: Project,
        task: Task,
        archive_month: str,
        archive_project_folder: str,
    ) -> Path:
        src = self.project_path(project) / task.folder_name
        if not src.is_dir():
            raise FilesystemError(f"Папка заявки не найдена: {src}")

        project_dir = self.archive_root() / archive_month / archive_project_folder
        project_dir.mkdir(parents=True, exist_ok=True)
        dest = project_dir / task.folder_name
        if dest.exists():
            raise FilesystemError(f"В архиве уже есть папка: {dest}")
        shutil.move(str(src), str(dest))
        return dest

    def restore_task(self, project: Project, task: Task) -> Path:
        """Move archived folder back under the project."""
        src = self.resolve_archived_task_path(task)
        if not src.is_dir():
            raise FilesystemError(f"Папка в архиве не найдена: {src}")
        self.ensure_project(project)
        dest = self.project_path(project) / task.folder_name
        if dest.exists():
            raise FilesystemError(f"Папка заявки уже существует: {dest}")
        shutil.move(str(src), str(dest))
        return dest

    def migrate_archived_folder(self, task: Task) -> Path | None:
        """Move ``{month}/{folder}`` → ``{month}/{project}/{folder}`` when needed."""
        if not task.archive_month or not task.archive_project_folder:
            return None
        preferred = self.archived_task_path(task)
        if preferred.is_dir():
            return preferred
        legacy = self.legacy_archived_task_path(task)
        if not legacy.is_dir():
            return None
        preferred.parent.mkdir(parents=True, exist_ok=True)
        if preferred.exists():
            raise FilesystemError(f"В архиве уже есть папка: {preferred}")
        shutil.move(str(legacy), str(preferred))
        return preferred

    def remove_task_folder(self, project: Project, task: Task) -> None:
        path = self.task_path(project, task)
        if path.is_dir():
            shutil.rmtree(path)

    def missing_task_folders(
        self, project: Project, tasks: list[Task]
    ) -> list[Task]:
        missing: list[Task] = []
        for task in tasks:
            if not task.has_folder:
                continue
            try:
                path = self.task_path(project, task)
            except FilesystemError:
                missing.append(task)
                continue
            if not path.is_dir():
                missing.append(task)
        return missing
