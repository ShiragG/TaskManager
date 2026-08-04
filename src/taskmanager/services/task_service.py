from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from taskmanager.domain import Directory, Link, Task, TaskStatus, make_folder_name
from taskmanager.infrastructure.filesystem import TaskFilesystem
from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.services.settings_service import Settings


class ServiceError(Exception):
    """Business rule or orchestration failure."""


@dataclass
class CreateTaskRequest:
    directory_id: int
    number: str
    description: str = ""
    date_end: date | None = None
    color: str = "#ffffff"
    hidden: bool = False
    by_template: bool = False
    links: list[tuple[str, str]] | None = None


@dataclass
class UpdateTaskRequest:
    number: str | None = None
    description: str | None = None
    date_end: date | None = None
    color: str | None = None
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
        return directory

    def rename_directory(self, directory_id: int, new_name: str) -> Directory:
        new_name = new_name.strip()
        if not new_name:
            raise ServiceError("Имя директории не может быть пустым")
        directory = self._require_directory(directory_id)
        existing = self.repo.get_directory_by_name(new_name)
        if existing and existing.id != directory_id:
            raise ServiceError(f"Директория «{new_name}» уже существует")
        self.fs.rename_directory(directory, new_name)
        self.repo.rename_directory(directory_id, new_name)
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

    # --- tasks ---

    def list_tasks(
        self,
        directory_id: int,
        *,
        include_hidden: bool = True,
        query: str | None = None,
    ) -> list[Task]:
        return self.repo.list_tasks(
            directory_id,
            status=TaskStatus.ACTIVE,
            include_hidden=include_hidden,
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
        folder_name = make_folder_name(number, request.description)
        self.fs.ensure_directory(directory)
        self.fs.create_task_folder(
            directory, folder_name, by_template=request.by_template
        )
        task = Task(
            id=None,
            directory_id=directory.id,  # type: ignore[arg-type]
            number=number,
            description=request.description.strip(),
            folder_name=folder_name,
            status=TaskStatus.ACTIVE,
            date_end=request.date_end,
            color=request.color,
            hidden=request.hidden,
            created_at=datetime.now(),
        )
        try:
            task = self.repo.add_task(task)
            if request.links is not None:
                links = [Link(None, task.id, n, t) for n, t in request.links]
                task.links = self.repo.replace_links(task.id, links)  # type: ignore[arg-type]
        except Exception:
            # Best-effort rollback of folder if DB insert fails
            try:
                self.fs.remove_task_folder(directory, task)
            except Exception:
                pass
            raise
        return task

    def update_task(self, task_id: int, request: UpdateTaskRequest) -> Task:
        task = self.get_task(task_id)
        if task.status != TaskStatus.ACTIVE:
            raise ServiceError("Нельзя редактировать архивную заявку")

        # folder_name stays fixed — metadata only
        if request.number is not None:
            number = request.number.strip()
            if not number:
                raise ServiceError("Номер заявки не может быть пустым")
            task.number = number
        if request.description is not None:
            task.description = request.description.strip()
        if request.clear_date_end:
            task.date_end = None
        elif request.date_end is not None:
            task.date_end = request.date_end
        if request.color is not None:
            task.color = request.color
        if request.hidden is not None:
            task.hidden = request.hidden

        self.repo.update_task(task)
        if request.links is not None:
            links = [Link(None, task.id, n, t) for n, t in request.links]
            task.links = self.repo.replace_links(task.id, links)  # type: ignore[arg-type]
        else:
            task.links = self.repo.list_links(task.id)  # type: ignore[arg-type]
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
        return task

    def delete_task(self, task_id: int, *, remove_folder: bool = True) -> None:
        task = self.get_task(task_id)
        directory = self._require_directory(task.directory_id)
        if remove_folder:
            try:
                self.fs.remove_task_folder(directory, task)
            except Exception as exc:
                raise ServiceError(f"Не удалось удалить папку заявки: {exc}") from exc
        self.repo.delete_task(task_id)

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
