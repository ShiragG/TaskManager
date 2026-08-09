from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from taskmanager.domain import (
    Link,
    Project,
    Task,
    TaskStatus,
    clamp_priority,
    make_folder_name,
    sanitize_for_folder,
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
    project_id: int
    number: str
    description: str = ""
    comment: str = ""
    date_end: date | None = None
    color: str | None = None
    priority: int = 10
    hidden: bool = False
    by_template: bool = False
    create_notes_file: bool = False
    create_folder: bool | None = None
    links: list[tuple[str, str]] | None = None
    source_module_id: str | None = None
    external_id: str | None = None
    source_label: str | None = None


@dataclass
class UpdateTaskRequest:
    number: str | None = None
    description: str | None = None
    comment: str | None = None
    date_end: date | None = None
    color: str | None = None
    clear_color: bool = False
    priority: int | None = None
    hidden: bool | None = None
    has_folder: bool | None = None
    links: list[tuple[str, str]] | None = None
    clear_date_end: bool = False
    source_module_id: str | None = None
    external_id: str | None = None
    source_label: str | None = None
    clear_source: bool = False


class TaskService:
    """CRUD for projects and tasks, including template copy and archive."""

    def __init__(
        self,
        repo: SqliteRepository,
        settings: Settings,
        filesystem: TaskFilesystem | None = None,
    ) -> None:
        self.repo = repo
        self.settings = settings
        self.fs = filesystem or TaskFilesystem(settings)
        self.migrate_archive_layout()

    # --- projects ---

    def list_projects(self) -> list[Project]:
        return self.repo.list_projects()

    def reorder_projects(self, project_ids: list[int]) -> None:
        """Persist project tab order (ids in display order)."""
        known = {p.id for p in self.repo.list_projects()}
        if set(project_ids) != known:
            raise ServiceError("Неполный список проектов для сортировки")
        self.repo.reorder_projects(project_ids)
        logger.debug("Reordered projects: %s", project_ids)

    @staticmethod
    def archive_project_folder_name(project: Project) -> str:
        """Sanitize project name at archive time for the archive subdirectory."""
        name = sanitize_for_folder(project.name.strip())
        if name:
            return name
        return f"project_{project.id}"

    def migrate_archive_layout(self) -> None:
        """Backfill ``archive_project_folder`` and move legacy archive folders."""
        archived = self.repo.list_tasks(status=TaskStatus.ARCHIVED)
        for task in archived:
            project = self.repo.get_project(task.project_id)
            if project is None:
                continue
            changed = False
            if not task.archive_project_folder:
                task.archive_project_folder = self.archive_project_folder_name(project)
                changed = True
            if changed:
                self.repo.update_task(task)
            if task.has_folder and task.archive_month and task.archive_project_folder:
                try:
                    self.fs.migrate_archived_folder(task)
                except FilesystemError as exc:
                    logger.warning(
                        "Archive folder migration failed for task id=%s: %s",
                        task.id,
                        exc,
                    )
    def create_project(self, name: str) -> Project:
        name = name.strip()
        if not name:
            raise ServiceError("Имя проекта не может быть пустым")
        if self.repo.get_project_by_name(name):
            raise ServiceError(f"Проект «{name}» уже существует")
        reserved = {self.settings.template_name, self.settings.archive_name}
        if name in reserved:
            raise ServiceError(f"Имя «{name}» зарезервировано настройками")
        project = self.repo.add_project(name)
        # Project folder is created lazily on first foldered task / open folder
        logger.debug("Created project id=%s name=%r", project.id, name)
        return project

    def rename_project(self, project_id: int, new_name: str) -> Project:
        new_name = new_name.strip()
        if not new_name:
            raise ServiceError("Имя проекта не может быть пустым")
        project = self._require_project(project_id)
        existing = self.repo.get_project_by_name(new_name)
        if existing and existing.id != project_id:
            raise ServiceError(f"Проект «{new_name}» уже существует")
        old_name = project.name
        try:
            self.fs.rename_project(project, new_name)
        except FilesystemError as exc:
            raise ServiceError(str(exc)) from exc
        self.repo.rename_project(project_id, new_name)
        logger.debug(
            "Renamed project id=%s %r -> %r", project_id, old_name, new_name
        )
        return self._require_project(project_id)

    def delete_project(self, project_id: int, *, remove_folder: bool = False) -> None:
        project = self._require_project(project_id)
        active = self.repo.list_tasks(project_id, status=TaskStatus.ACTIVE)
        if active:
            raise ServiceError(
                "Нельзя удалить проект с активными заявками — сначала заархивируйте их"
            )
        self.repo.delete_project(project_id)
        if remove_folder:
            path = self.fs.project_path(project)
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
        logger.debug("Deleted project id=%s name=%r", project_id, project.name)

    # --- tasks ---

    def list_tasks(
        self,
        project_id: int,
        *,
        only_hidden: bool = False,
        archived: bool = False,
        query: str | None = None,
    ) -> list[Task]:
        status = TaskStatus.ARCHIVED if archived else TaskStatus.ACTIVE
        only_hidden_filter: bool | None
        if archived:
            only_hidden_filter = None
        else:
            only_hidden_filter = only_hidden
        return self.repo.list_tasks(
            project_id,
            status=status,
            only_hidden=only_hidden_filter,
            query=query,
        )

    def validate_create_folder(
        self,
        project_id: int,
        number: str,
        *,
        create_folder: bool,
        by_template: bool = False,
    ) -> None:
        """Pre-flight checks before creating a task (keeps dialog open on failure)."""
        number = number.strip()
        if not number:
            raise ServiceError("Номер заявки не может быть пустым")
        folder_name = make_folder_name(number)
        if not folder_name:
            raise ServiceError("Номер заявки содержит только недопустимые символы")
        project = self._require_project(project_id)
        conflict = self.repo.find_task_by_number(project.id, number)  # type: ignore[arg-type]
        if conflict is not None:
            raise ServiceError(f"Заявка с номером «{number}» уже существует")
        need_folder = create_folder or by_template
        if not need_folder:
            return
        try:
            self.fs.validate_create_task_folder(
                project, folder_name, by_template=by_template
            )
        except FilesystemError as exc:
            raise ServiceError(str(exc)) from exc

    def validate_update_folder(self, task_id: int, number: str) -> None:
        """Pre-flight checks before updating a task number / folder rename."""
        task = self.get_task(task_id)
        if task.status != TaskStatus.ACTIVE:
            raise ServiceError("Нельзя редактировать архивную заявку")
        number = number.strip()
        if not number:
            raise ServiceError("Номер заявки не может быть пустым")
        new_folder_name = make_folder_name(number)
        if not new_folder_name:
            raise ServiceError("Номер заявки содержит только недопустимые символы")
        if number != task.number:
            conflict = self.repo.find_task_by_number(task.project_id, number)
            if conflict is not None and conflict.id != task.id:
                raise ServiceError(f"Заявка с номером «{number}» уже существует")
        if not task.has_folder or new_folder_name == task.folder_name:
            return
        project = self._require_project(task.project_id)
        try:
            self.fs.validate_rename_task_folder(project, task, new_folder_name)
        except FilesystemError as exc:
            raise ServiceError(str(exc)) from exc

    def get_task(self, task_id: int) -> Task:
        task = self.repo.get_task(task_id)
        if task is None:
            raise ServiceError("Заявка не найдена")
        return task

    def create_task(self, request: CreateTaskRequest) -> Task:
        project = self._require_project(request.project_id)
        number = request.number.strip()
        if not number:
            raise ServiceError("Номер заявки не может быть пустым")
        folder_name = make_folder_name(number)
        if not folder_name:
            raise ServiceError("Номер заявки содержит только недопустимые символы")
        conflict = self.repo.find_task_by_number(project.id, number)  # type: ignore[arg-type]
        if conflict is not None:
            raise ServiceError(f"Заявка с номером «{number}» уже существует")

        create_folder = (
            self.settings.create_task_folder
            if request.create_folder is None
            else request.create_folder
        )
        if request.by_template or request.create_notes_file:
            create_folder = True

        link_pairs: list[tuple[str, str]] = list(request.links or [])
        folder_path: Path | None = None

        if create_folder:
            try:
                folder_path = self.fs.create_task_folder(
                    project, folder_name, by_template=request.by_template
                )
            except FilesystemError as exc:
                raise ServiceError(str(exc)) from exc
            if request.create_notes_file:
                try:
                    notes_path = self.fs.ensure_notes_file(folder_path)
                except OSError as exc:
                    raise ServiceError(f"Не удалось создать файл заметок: {exc}") from exc
                link_pairs.append((NOTES_LINK_NAME, str(notes_path)))

        task = Task(
            id=None,
            project_id=project.id,  # type: ignore[arg-type]
            number=number,
            description=request.description,
            comment=request.comment,
            folder_name=folder_name,
            status=TaskStatus.ACTIVE,
            date_end=request.date_end,
            color=request.color,
            priority=clamp_priority(request.priority),
            hidden=request.hidden,
            has_folder=create_folder,
            created_at=datetime.now(),
            source_module_id=request.source_module_id,
            external_id=request.external_id,
            source_label=request.source_label,
        )
        try:
            task = self.repo.add_task(task)
            if link_pairs:
                links = [Link(None, task.id, n, t) for n, t in link_pairs]
                task.links = self.repo.replace_links(task.id, links)  # type: ignore[arg-type]
        except Exception:
            logger.exception("Failed to persist new task number=%r", number)
            if create_folder:
                try:
                    self.fs.remove_task_folder(project, task)
                except Exception:
                    pass
            raise
        logger.debug(
            "Created task id=%s number=%r project=%s has_folder=%s priority=%s",
            task.id,
            task.number,
            task.project_id,
            task.has_folder,
            task.priority,
        )
        return task

    def update_task(self, task_id: int, request: UpdateTaskRequest) -> Task:
        task = self.get_task(task_id)
        if task.status != TaskStatus.ACTIVE:
            raise ServiceError("Нельзя редактировать архивную заявку")

        project = self._require_project(task.project_id)
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
                conflict = self.repo.find_task_by_number(task.project_id, number)
                if conflict is not None and conflict.id != task.id:
                    raise ServiceError(f"Заявка с номером «{number}» уже существует")
            if new_folder_name != task.folder_name:
                if task.has_folder:
                    try:
                        self.fs.rename_task_folder(project, task, new_folder_name)
                    except FilesystemError as exc:
                        raise ServiceError(str(exc)) from exc
                    renamed = True
                task.folder_name = new_folder_name
            task.number = number

        if request.description is not None:
            task.description = request.description
        if request.comment is not None:
            task.comment = request.comment
        if request.clear_date_end:
            task.date_end = None
        elif request.date_end is not None:
            task.date_end = request.date_end
        if request.clear_color:
            task.color = None
        elif request.color is not None:
            task.color = request.color
        if request.priority is not None:
            task.priority = clamp_priority(request.priority)
        if request.hidden is not None:
            task.hidden = request.hidden
        if request.has_folder is not None:
            task.has_folder = request.has_folder
        if request.clear_source:
            task.source_module_id = None
            task.external_id = None
            task.source_label = None
        else:
            if request.source_module_id is not None:
                task.source_module_id = request.source_module_id
            if request.external_id is not None:
                task.external_id = request.external_id
            if request.source_label is not None:
                task.source_label = request.source_label

        try:
            self.repo.update_task(task)
        except Exception:
            logger.exception("Failed to update task id=%s", task_id)
            if renamed:
                try:
                    self.fs.rename_task_folder(project, task, old_folder_name)
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
        project = self._require_project(task.project_id)
        archive_month = datetime.now().strftime("%Y_%m")
        archive_project_folder = self.archive_project_folder_name(project)
        if task.has_folder:
            try:
                self.fs.archive_task(
                    project, task, archive_month, archive_project_folder
                )
            except FilesystemError as exc:
                raise ServiceError(str(exc)) from exc
        task.status = TaskStatus.ARCHIVED
        task.archive_month = archive_month
        task.archive_project_folder = archive_project_folder
        self.repo.update_task(task)
        logger.debug(
            "Archived task id=%s number=%r month=%s project_folder=%r has_folder=%s",
            task.id,
            task.number,
            archive_month,
            archive_project_folder,
            task.has_folder,
        )
        return task

    def restore_task(self, task_id: int) -> Task:
        task = self.get_task(task_id)
        if task.status != TaskStatus.ARCHIVED:
            raise ServiceError("Заявка не в архиве")
        project = self._require_project(task.project_id)
        if task.has_folder:
            try:
                self.fs.restore_task(project, task)
            except FilesystemError as exc:
                raise ServiceError(str(exc)) from exc
        task.status = TaskStatus.ACTIVE
        task.archive_month = None
        task.archive_project_folder = None
        self.repo.update_task(task)
        logger.debug(
            "Restored task id=%s number=%r has_folder=%s",
            task.id,
            task.number,
            task.has_folder,
        )
        return task

    def delete_task(self, task_id: int, *, remove_folder: bool = True) -> None:
        task = self.get_task(task_id)
        project = self._require_project(task.project_id)
        if remove_folder and task.has_folder:
            try:
                self.fs.remove_task_folder(project, task)
            except Exception as exc:
                logger.exception("Failed to remove task folder id=%s", task_id)
                raise ServiceError(f"Не удалось удалить папку заявки: {exc}") from exc
        self.repo.delete_task(task_id)
        logger.debug("Deleted task id=%s number=%r", task_id, task.number)

    def search(self, query: str, *, archived: bool = False) -> list[Task]:
        query = query.strip()
        if not query:
            return []
        status = TaskStatus.ARCHIVED if archived else TaskStatus.ACTIVE
        return self.repo.search_tasks(query, status=status)

    def task_folder_path(self, task_id: int) -> Path:
        task = self.get_task(task_id)
        project = self._require_project(task.project_id)
        return self.fs.task_path(project, task)

    def open_task_folder(self, task_id: int) -> Path:
        """Ensure task folder exists (creating if needed), set has_folder, return path."""
        task = self.get_task(task_id)
        project = self._require_project(task.project_id)
        if task.status == TaskStatus.ARCHIVED and task.has_folder:
            path = self.fs.task_path(project, task)
            if not path.is_dir():
                raise ServiceError(f"Папка в архиве не найдена: {path}")
            return path
        try:
            path = self.fs.ensure_task_folder(project, task)
        except FilesystemError as exc:
            raise ServiceError(str(exc)) from exc
        if not task.has_folder:
            task.has_folder = True
            self.repo.update_task(task)
        return path

    def recreate_task_folder(self, task_id: int) -> Path:
        """Recreate a missing folder for a has_folder task (empty, no template)."""
        return self.open_task_folder(task_id)

    def clear_task_folder_flag(self, task_id: int) -> Task:
        task = self.get_task(task_id)
        task.has_folder = False
        self.repo.update_task(task)
        logger.debug("Cleared has_folder for task id=%s", task_id)
        return task

    def project_folder_path(self, project_id: int) -> Path:
        project = self._require_project(project_id)
        return self.fs.ensure_project(project)

    def check_missing_folders(self) -> list[tuple[Project, Task]]:
        """Return (project, task) pairs with has_folder whose folders are missing."""
        missing: list[tuple[Project, Task]] = []
        for project in self.repo.list_projects():
            tasks = self.repo.list_tasks(project.id, status=TaskStatus.ACTIVE)  # type: ignore[arg-type]
            for task in self.fs.missing_task_folders(project, tasks):
                missing.append((project, task))
        return missing

    def _require_project(self, project_id: int) -> Project:
        project = self.repo.get_project(project_id)
        if project is None:
            raise ServiceError("Проект не найден")
        return project
