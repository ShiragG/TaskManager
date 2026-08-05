from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from taskmanager.domain import (
    Directory,
    Link,
    Task,
    TaskStatus,
    clamp_priority,
    make_folder_name,
)
from taskmanager.infrastructure.filesystem import (
    NOTES_LINK_NAME,
    FilesystemError,
    TaskFilesystem,
)
from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.services.settings_service import Settings

logger = logging.getLogger(__name__)


class ServiceError(Exception):
    """Business rule or orchestration failure."""


@dataclass
class CreateTaskRequest:
    directory_id: int
    number: str
    description: str = ""
    date_end: date | None = None
    color: str = "#ffffff"
    priority: int = 10
    hidden: bool = False
    by_template: bool = False
    create_notes_file: bool = False
    links: list[tuple[str, str]] | None = None


@dataclass
class UpdateTaskRequest:
    number: str | None = None
    description: str | None = None
    date_end: date | None = None
    color: str | None = None
    priority: int | None = None
    hidden: bool | None = None
    links: list[tuple[str, str]] | None = None
    clear_date_end: bool = False


class TaskService:
    """CRUD for directories and tasks, including template copy and archive."""

    def __init__(
        self,
        repo: SqliteRepository,
        settings: Settings,
        filesystem: TaskFilesystem | None = None,
    ) -> None:
        self.repo = repo
        self.settings = settings
        self.fs = filesystem or TaskFilesystem(settings)

    # --- directories ---

    def list_directories(self) -> list[Directory]:
        return self.repo.list_directories()

    def create_directory(self, name: str) -> Directory:
        name = name.strip()
        if not name:
            raise ServiceError("Имя директории не может быть пустым")
        if self.repo.get_directory_by_name(name):
            raise ServiceError(f"Директория «{name}» уже существует")
        reserved = {self.settings.template_name, self.settings.archive_name}
        if name in reserved:
            raise ServiceError(f"Имя «{name}» зарезервировано настройками")
        directory = self.repo.add_directory(name)
        self.fs.ensure_directory(directory)
        logger.debug("Created directory id=%s name=%r", directory.id, name)
        return directory

    def rename_directory(self, directory_id: int, new_name: str) -> Directory:
        new_name = new_name.strip()
        if not new_name:
            raise ServiceError("Имя директории не может быть пустым")
        directory = self._require_directory(directory_id)
        existing = self.repo.get_directory_by_name(new_name)
        if existing and existing.id != directory_id:
            raise ServiceError(f"Директория «{new_name}» уже существует")
        old_name = directory.name
        self.fs.rename_directory(directory, new_name)
        self.repo.rename_directory(directory_id, new_name)
        logger.debug(
            "Renamed directory id=%s %r -> %r", directory_id, old_name, new_name
        )
        return self._require_directory(directory_id)

    def delete_directory(self, directory_id: int, *, remove_folder: bool = False) -> None:
        directory = self._require_directory(directory_id)
        active = self.repo.list_tasks(directory_id, status=TaskStatus.ACTIVE)
        if active:
            raise ServiceError(
                "Нельзя удалить директорию с активными заявками — сначала заархивируйте их"
            )
        self.repo.delete_directory(directory_id)
        if remove_folder:
            path = self.fs.directory_path(directory)
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
        logger.debug("Deleted directory id=%s name=%r", directory_id, directory.name)

    # --- tasks ---

    def list_tasks(
        self,
        directory_id: int,
        *,
        only_hidden: bool = False,
        query: str | None = None,
    ) -> list[Task]:
        return self.repo.list_tasks(
            directory_id,
            status=TaskStatus.ACTIVE,
            only_hidden=only_hidden,
            query=query,
        )

    def get_task(self, task_id: int) -> Task:
        task = self.repo.get_task(task_id)
        if task is None:
            raise ServiceError("Заявка не найдена")
        return task

    def create_task(self, request: CreateTaskRequest) -> Task:
        directory = self._require_directory(request.directory_id)
        number = request.number.strip()
        if not number:
            raise ServiceError("Номер заявки не может быть пустым")
        folder_name = make_folder_name(number)
        if not folder_name:
            raise ServiceError("Номер заявки содержит только недопустимые символы")
        conflict = self.repo.find_task_by_number(directory.id, number)  # type: ignore[arg-type]
        if conflict is not None:
            raise ServiceError(f"Заявка с номером «{number}» уже существует")
        self.fs.ensure_directory(directory)
        try:
            folder_path = self.fs.create_task_folder(
                directory, folder_name, by_template=request.by_template
            )
        except FilesystemError as exc:
            raise ServiceError(str(exc)) from exc

        link_pairs: list[tuple[str, str]] = list(request.links or [])
        if request.create_notes_file:
            try:
                notes_path = self.fs.ensure_notes_file(folder_path)
            except OSError as exc:
                raise ServiceError(f"Не удалось создать файл заметок: {exc}") from exc
            link_pairs.append((NOTES_LINK_NAME, str(notes_path)))

        task = Task(
            id=None,
            directory_id=directory.id,  # type: ignore[arg-type]
            number=number,
            description=request.description.strip(),
            folder_name=folder_name,
            status=TaskStatus.ACTIVE,
            date_end=request.date_end,
            color=request.color,
            priority=clamp_priority(request.priority),
            hidden=request.hidden,
            created_at=datetime.now(),
        )
        try:
            task = self.repo.add_task(task)
            if link_pairs:
                links = [Link(None, task.id, n, t) for n, t in link_pairs]
                task.links = self.repo.replace_links(task.id, links)  # type: ignore[arg-type]
        except Exception:
            logger.exception("Failed to persist new task number=%r", number)
            # Best-effort rollback of folder if DB insert fails
            try:
                self.fs.remove_task_folder(directory, task)
            except Exception:
                pass
            raise
        logger.debug(
            "Created task id=%s number=%r dir=%s priority=%s",
            task.id,
            task.number,
            task.directory_id,
            task.priority,
        )
        return task

    def update_task(self, task_id: int, request: UpdateTaskRequest) -> Task:
        task = self.get_task(task_id)
        if task.status != TaskStatus.ACTIVE:
            raise ServiceError("Нельзя редактировать архивную заявку")

        directory = self._require_directory(task.directory_id)
        old_folder_name = task.folder_name
        renamed = False

        if request.number is not None:
            number = request.number.strip()
            if not number:
                raise ServiceError("Номер заявки не может быть пустым")
            new_folder_name = make_folder_name(number)
            if not new_folder_name:
                raise ServiceError("Номер заявки содержит только недопустимые символы")
            if number != task.number:
                conflict = self.repo.find_task_by_number(task.directory_id, number)
                if conflict is not None and conflict.id != task.id:
                    raise ServiceError(f"Заявка с номером «{number}» уже существует")
            if new_folder_name != task.folder_name:
                try:
                    self.fs.rename_task_folder(directory, task, new_folder_name)
                except FilesystemError as exc:
                    raise ServiceError(str(exc)) from exc
                renamed = True
                task.folder_name = new_folder_name
            task.number = number

        if request.description is not None:
            task.description = request.description.strip()
        if request.clear_date_end:
            task.date_end = None
        elif request.date_end is not None:
            task.date_end = request.date_end
        if request.color is not None:
            task.color = request.color
        if request.priority is not None:
            task.priority = clamp_priority(request.priority)
        if request.hidden is not None:
            task.hidden = request.hidden

        try:
            self.repo.update_task(task)
        except Exception:
            logger.exception("Failed to update task id=%s", task_id)
            if renamed:
                try:
                    self.fs.rename_task_folder(directory, task, old_folder_name)
                    task.folder_name = old_folder_name
                except Exception:
                    pass
            raise

        if request.links is not None:
            links = [Link(None, task.id, n, t) for n, t in request.links]
            task.links = self.repo.replace_links(task.id, links)  # type: ignore[arg-type]
        else:
            task.links = self.repo.list_links(task.id)  # type: ignore[arg-type]
        logger.debug("Updated task id=%s number=%r", task.id, task.number)
        return task

    def archive_task(self, task_id: int) -> Task:
        task = self.get_task(task_id)
        if task.status == TaskStatus.ARCHIVED:
            raise ServiceError("Заявка уже в архиве")
        directory = self._require_directory(task.directory_id)
        archive_month = datetime.now().strftime("%Y_%m")
        # Move while still active so path resolves under directory
        self.fs.archive_task(directory, task, archive_month)
        task.status = TaskStatus.ARCHIVED
        task.archive_month = archive_month
        self.repo.update_task(task)
        logger.debug(
            "Archived task id=%s number=%r month=%s",
            task.id,
            task.number,
            archive_month,
        )
        return task

    def delete_task(self, task_id: int, *, remove_folder: bool = True) -> None:
        task = self.get_task(task_id)
        directory = self._require_directory(task.directory_id)
        if remove_folder:
            try:
                self.fs.remove_task_folder(directory, task)
            except Exception as exc:
                logger.exception("Failed to remove task folder id=%s", task_id)
                raise ServiceError(f"Не удалось удалить папку заявки: {exc}") from exc
        self.repo.delete_task(task_id)
        logger.debug("Deleted task id=%s number=%r", task_id, task.number)

    def search(self, query: str) -> list[Task]:
        query = query.strip()
        if not query:
            return []
        return self.repo.search_tasks(query, status=TaskStatus.ACTIVE)

    def task_folder_path(self, task_id: int) -> Path:
        task = self.get_task(task_id)
        directory = self._require_directory(task.directory_id)
        return self.fs.task_path(directory, task)

    def directory_folder_path(self, directory_id: int) -> Path:
        directory = self._require_directory(directory_id)
        path = self.fs.ensure_directory(directory)
        return path

    def check_missing_folders(self) -> list[tuple[Directory, Task]]:
        """Return (directory, task) pairs whose folders are missing on disk."""
        missing: list[tuple[Directory, Task]] = []
        for directory in self.repo.list_directories():
            tasks = self.repo.list_tasks(directory.id, status=TaskStatus.ACTIVE)  # type: ignore[arg-type]
            for task in self.fs.missing_task_folders(directory, tasks):
                missing.append((directory, task))
        return missing

    def _require_directory(self, directory_id: int) -> Directory:
        directory = self.repo.get_directory(directory_id)
        if directory is None:
            raise ServiceError("Директория не найдена")
        return directory
