from __future__ import annotations

import shutil
from pathlib import Path

from taskmanager.domain import Directory, Task, TaskStatus
from taskmanager.services.settings_service import Settings


class FilesystemError(Exception):
    """Filesystem operation failed."""


class TaskFilesystem:
    """Resolve and mutate task/directory folders on disk."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def work_dir(self) -> Path:
        return Path(self.settings.work_dir)

    def directory_path(self, directory: Directory) -> Path:
        return self.work_dir / directory.name

    def template_path(self, directory: Directory) -> Path:
        return self.directory_path(directory) / self.settings.template_name

    def archive_root(self) -> Path:
        return self.work_dir / self.settings.archive_name

    def task_path(self, directory: Directory, task: Task) -> Path:
        if task.status == TaskStatus.ARCHIVED:
            if not task.archive_month:
                raise FilesystemError(
                    f"У архивной заявки {task.number} не указан месяц архива"
                )
            return self.archive_root() / task.archive_month / task.folder_name
        return self.directory_path(directory) / task.folder_name

    def ensure_directory(self, directory: Directory) -> Path:
        path = self.directory_path(directory)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def rename_directory(self, old: Directory, new_name: str) -> Path:
        old_path = self.directory_path(old)
        new_path = self.work_dir / new_name
        if old_path == new_path:
            return new_path
        if not old_path.is_dir():
            raise FilesystemError(f"Папка директории не найдена: {old_path}")
        if new_path.exists():
            raise FilesystemError(f"Папка уже существует: {new_path}")
        old_path.rename(new_path)
        return new_path

    def create_task_folder(
        self,
        directory: Directory,
        folder_name: str,
        *,
        by_template: bool,
    ) -> Path:
        dest = self.directory_path(directory) / folder_name
        if dest.exists():
            raise FilesystemError(f"Папка заявки уже существует: {dest}")

        if by_template:
            template = self.template_path(directory)
            if not template.is_dir():
                raise FilesystemError(
                    f"Не найден шаблон «{self.settings.template_name}» "
                    f"в директории «{directory.name}»"
                )
            shutil.copytree(template, dest)
        else:
            dest.mkdir(parents=True)
        return dest

    def rename_task_folder(
        self,
        directory: Directory,
        task: Task,
        new_folder_name: str,
    ) -> Path:
        src = self.task_path(directory, task)
        dest = self.directory_path(directory) / new_folder_name
        if src == dest:
            return dest
        if not src.is_dir():
            raise FilesystemError(f"Папка заявки не найдена: {src}")
        if dest.exists():
            raise FilesystemError(f"Папка заявки уже существует: {dest}")
        src.rename(dest)
        return dest

    def archive_task(self, directory: Directory, task: Task, archive_month: str) -> Path:
        src = self.task_path(directory, task)
        if not src.is_dir():
            raise FilesystemError(f"Папка заявки не найдена: {src}")

        month_dir = self.archive_root() / archive_month
        month_dir.mkdir(parents=True, exist_ok=True)
        dest = month_dir / task.folder_name
        if dest.exists():
            raise FilesystemError(f"В архиве уже есть папка: {dest}")
        shutil.move(str(src), str(dest))
        return dest

    def remove_task_folder(self, directory: Directory, task: Task) -> None:
        path = self.task_path(directory, task)
        if path.is_dir():
            shutil.rmtree(path)

    def missing_task_folders(
        self, directory: Directory, tasks: list[Task]
    ) -> list[Task]:
        missing: list[Task] = []
        for task in tasks:
            try:
                path = self.task_path(directory, task)
            except FilesystemError:
                missing.append(task)
                continue
            if not path.is_dir():
                missing.append(task)
        return missing
