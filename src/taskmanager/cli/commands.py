from __future__ import annotations

from datetime import date, datetime
from html import escape
from pathlib import Path

from taskmanager.cli.html_plain import html_to_cli_plain
from taskmanager.cli.output import (
    emit_json,
    emit_json_value,
    emit_stdout,
    emit_table,
)
from taskmanager.domain import PRIORITY_DEFAULT, Project, Task
from taskmanager.services.excel_export import export_tasks_to_excel
from taskmanager.services.source_host import SourceHost
from taskmanager.services.source_protocol import SourceDraft
from taskmanager.services.task_service import (
    CreateTaskRequest,
    ServiceError,
    TaskService,
    UpdateTaskRequest,
)


class CliError(Exception):
    def __init__(self, message: str, code: str = "error") -> None:
        super().__init__(message)
        self.code = code


def require_project(service: TaskService, name: str) -> Project:
    try:
        return service.get_project_by_name(name)
    except ServiceError as exc:
        raise CliError(f"Project '{name}' not found", code="not_found") from exc


def require_task(service: TaskService, project_name: str, number: str) -> tuple[Project, Task]:
    project = require_project(service, project_name)
    if project.id is None:
        raise CliError(f"Project '{project_name}' not found", code="not_found")
    try:
        return project, service.get_task_by_number(project.id, number)
    except ServiceError as exc:
        raise CliError(
            f"Task '{number}' not found in project '{project_name}'",
            code="not_found",
        ) from exc


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CliError(
            f"invalid date: {value} (expected YYYY-MM-DD)",
            code="usage",
        ) from exc


def folder_path_or_none(service: TaskService, task: Task) -> str | None:
    if not task.has_folder or task.id is None:
        return None
    return str(service.task_folder_path(task.id))


def task_payload(service: TaskService, project: Project, task: Task) -> dict[str, object]:
    created = task.created_at.isoformat(timespec="seconds") if task.created_at else None
    return {
        "project": project.name,
        "number": task.number,
        "description": task.description,
        "description_plain": html_to_cli_plain(task.description),
        "comment": task.comment,
        "comment_plain": html_to_cli_plain(task.comment),
        "priority": task.priority,
        "status": task.status.value,
        "workflow_status": task.workflow_status.value,
        "hidden": task.hidden,
        "date_end": task.date_end.isoformat() if task.date_end else None,
        "color": task.color,
        "has_folder": task.has_folder,
        "created_at": created,
        "has_source": task.has_source,
        "source_module_id": task.source_module_id,
        "external_id": task.external_id,
        "source_label": task.source_label,
        "source_status_id": task.source_status_id,
        "source_status_label": task.source_status_label,
        "folder": folder_path_or_none(service, task),
        "links": [{"name": link.name, "target": link.target} for link in task.links],
    }


def source_draft_payload(draft: SourceDraft) -> dict[str, object]:
    return {
        "external_id": draft.external_id,
        "number": draft.number,
        "description": draft.description,
        "description_plain": html_to_cli_plain(draft.description),
        "priority": draft.priority,
        "source_label": draft.source_label,
        "source_status_id": draft.source_status_id,
        "source_status_label": draft.source_status_label,
        "files": [
            {"file_id": item.file_id, "name": item.name} for item in draft.files
        ],
        "links": [{"name": name, "target": target} for name, target in draft.links],
    }


def cmd_project_list(service: TaskService, json_mode: bool) -> int:
    projects = service.list_projects()
    emit_table(
        ["NAME"],
        [[p.name] for p in projects],
        json_mode=json_mode,
        json_rows=[{"name": p.name} for p in projects],
    )
    return 0


def cmd_project_create(service: TaskService, name: str, json_mode: bool) -> int:
    project = service.create_project(name)
    if json_mode:
        emit_json({"name": project.name})
    else:
        emit_stdout(project.name)
    return 0


def cmd_project_rename(
    service: TaskService, project_name: str, new_name: str, json_mode: bool
) -> int:
    project = require_project(service, project_name)
    renamed = service.rename_project(project.id, new_name)  # type: ignore[arg-type]
    if json_mode:
        emit_json({"name": renamed.name})
    else:
        emit_stdout(renamed.name)
    return 0


def cmd_project_delete(service: TaskService, project_name: str, json_mode: bool) -> int:
    project = require_project(service, project_name)
    service.delete_project(project.id)  # type: ignore[arg-type]
    if json_mode:
        emit_json({"deleted": project_name})
    return 0


def cmd_task_list(
    service: TaskService,
    project_name: str,
    *,
    hidden: bool,
    archived: bool,
    json_mode: bool,
) -> int:
    project = require_project(service, project_name)
    tasks = service.list_tasks(
        project.id,  # type: ignore[arg-type]
        only_hidden=hidden,
        archived=archived,
    )
    headers = (
        "PRIORITY",
        "NUMBER",
        "STATUS",
        "DATE_END",
        "DESCRIPTION",
        "COMMENT",
    )
    rows = [
        [
            task.priority,
            task.number,
            task.display_status,
            task.date_end.isoformat() if task.date_end else "",
            html_to_cli_plain(task.description),
            html_to_cli_plain(task.comment),
        ]
        for task in tasks
    ]
    json_rows = [
        {
            "priority": task.priority,
            "number": task.number,
            "status": task.display_status,
            "date_end": task.date_end.isoformat() if task.date_end else None,
            "description_plain": html_to_cli_plain(task.description),
            "comment_plain": html_to_cli_plain(task.comment),
        }
        for task in tasks
    ]
    emit_table(headers, rows, json_mode=json_mode, json_rows=json_rows)
    return 0


def cmd_task_search(
    service: TaskService,
    query: str,
    *,
    archived: bool,
    json_mode: bool,
) -> int:
    tasks = service.search(query, archived=archived)
    names = {p.id: p.name for p in service.list_projects() if p.id is not None}
    headers = (
        "PROJECT",
        "PRIORITY",
        "NUMBER",
        "STATUS",
        "DATE_END",
        "DESCRIPTION",
        "COMMENT",
    )
    rows = [
        [
            names.get(task.project_id, ""),
            task.priority,
            task.number,
            task.display_status,
            task.date_end.isoformat() if task.date_end else "",
            html_to_cli_plain(task.description),
            html_to_cli_plain(task.comment),
        ]
        for task in tasks
    ]
    json_rows = [
        {
            "project": names.get(task.project_id, ""),
            "priority": task.priority,
            "number": task.number,
            "status": task.display_status,
            "date_end": task.date_end.isoformat() if task.date_end else None,
            "description_plain": html_to_cli_plain(task.description),
            "comment_plain": html_to_cli_plain(task.comment),
        }
        for task in tasks
    ]
    emit_table(headers, rows, json_mode=json_mode, json_rows=json_rows)
    return 0


def cmd_task_get(
    service: TaskService,
    project_name: str,
    number: str,
    *,
    field: str | None,
    json_mode: bool,
) -> int:
    project, task = require_task(service, project_name, number)
    payload = task_payload(service, project, task)
    if field is not None:
        if field not in payload:
            raise CliError(f"Unknown field '{field}'", code="not_found")
        emit_json_value(payload[field])
        return 0
    emit_json(payload)
    return 0


def cmd_task_create(service: TaskService, args, json_mode: bool) -> int:
    project = require_project(service, args.project)
    proposed: str | None = None
    number = (args.number or "").strip()
    if not number:
        number = service.propose_next_number(project.id)  # type: ignore[arg-type]
        proposed = number
    date_end = parse_iso_date(args.date_end) if args.date_end else None
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id,  # type: ignore[arg-type]
            number=number,
            description=args.description or "",
            comment=args.comment or "",
            date_end=date_end,
            priority=PRIORITY_DEFAULT if args.priority is None else args.priority,
            hidden=bool(args.hidden),
            create_folder=bool(args.folder),
            workflow_status=args.status,
            proposed_number=proposed,
        )
    )
    payload = task_payload(service, project, task)
    if json_mode:
        emit_json(payload)
    else:
        emit_stdout(task.number)
    return 0


def cmd_task_update(service: TaskService, args, json_mode: bool) -> int:
    project, task = require_task(service, args.project, args.number)
    date_end = parse_iso_date(args.date_end) if args.date_end else None
    updated = service.update_task(
        task.id,  # type: ignore[arg-type]
        UpdateTaskRequest(
            number=args.new_number,
            description=args.description,
            comment=args.comment,
            date_end=date_end,
            priority=args.priority,
            workflow_status=args.status,
        ),
    )
    payload = task_payload(service, project, updated)
    if json_mode:
        emit_json(payload)
    else:
        emit_stdout(updated.number)
    return 0


def cmd_task_comment(service: TaskService, args, json_mode: bool) -> int:
    project, task = require_task(service, args.project, args.number)
    if args.comment_action == "set":
        comment = args.text
    else:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        block = f"<p>{stamp}\n{escape(args.text)}</p>"
        comment = (task.comment or "") + block
    updated = service.update_task(
        task.id,  # type: ignore[arg-type]
        UpdateTaskRequest(comment=comment),
    )
    payload = task_payload(service, project, updated)
    if json_mode:
        emit_json(payload)
    else:
        emit_stdout(updated.comment_plain)
    return 0


def cmd_task_archive(service: TaskService, args, json_mode: bool) -> int:
    project, task = require_task(service, args.project, args.number)
    updated = service.archive_task(task.id)  # type: ignore[arg-type]
    if json_mode:
        emit_json(task_payload(service, project, updated))
    return 0


def cmd_task_restore(service: TaskService, args, json_mode: bool) -> int:
    project, task = require_task(service, args.project, args.number)
    updated = service.restore_task(task.id)  # type: ignore[arg-type]
    if json_mode:
        emit_json(task_payload(service, project, updated))
    return 0


def cmd_task_hide(service: TaskService, args, *, hidden: bool, json_mode: bool) -> int:
    project, task = require_task(service, args.project, args.number)
    updated = service.update_task(
        task.id,  # type: ignore[arg-type]
        UpdateTaskRequest(hidden=hidden),
    )
    if json_mode:
        emit_json(task_payload(service, project, updated))
    return 0


def cmd_task_delete(service: TaskService, args, json_mode: bool) -> int:
    _project, task = require_task(service, args.project, args.number)
    service.delete_task(task.id)  # type: ignore[arg-type]
    if json_mode:
        emit_json({"deleted": args.number, "project": args.project})
    return 0


def cmd_task_folder(service: TaskService, args, json_mode: bool) -> int:
    _project, task = require_task(service, args.project, args.number)
    ensure = args.folder_action == "ensure"
    if not ensure and not task.has_folder:
        raise CliError(
            f"Task '{args.number}' has no folder",
            code="no_folder",
        )
    if task.id is None:
        raise CliError(
            f"Task '{args.number}' not found in project '{args.project}'",
            code="not_found",
        )
    path = (
        service.recreate_task_folder(task.id)
        if ensure
        else service.task_folder_path(task.id)
    )
    if json_mode:
        emit_json({"folder": str(path)})
    else:
        emit_stdout(str(path))
    return 0


def cmd_task_excel(service: TaskService, args, json_mode: bool) -> int:
    project = require_project(service, args.project)
    dest = Path(args.output)
    path = export_tasks_to_excel(
        service,
        dest,
        project_ids=[project.id],  # type: ignore[list-item]
    )
    if json_mode:
        emit_json({"output": str(path)})
    else:
        emit_stdout(str(path))
    return 0


def cmd_link_list(service: TaskService, args, json_mode: bool) -> int:
    _project, task = require_task(service, args.project, args.number)
    rows = [[link.name, link.target] for link in task.links]
    json_rows = [{"name": link.name, "target": link.target} for link in task.links]
    emit_table(
        ["NAME", "TARGET"],
        rows,
        json_mode=json_mode,
        json_rows=json_rows,
    )
    return 0


def cmd_link_add(service: TaskService, args, json_mode: bool) -> int:
    project, task = require_task(service, args.project, args.number)
    name = args.name.strip()
    target = args.target.strip()
    if not name:
        raise CliError("Link name cannot be empty", code="error")
    if not target:
        raise CliError("Link target cannot be empty", code="error")
    existing = [(link.name, link.target) for link in task.links]
    if any(link_name == name for link_name, _target in existing):
        raise CliError(f"Link '{name}' already exists", code="error")
    existing.append((name, target))
    updated = service.update_task(
        task.id,  # type: ignore[arg-type]
        UpdateTaskRequest(links=existing),
    )
    if json_mode:
        emit_json(task_payload(service, project, updated))
    return 0


def cmd_link_remove(service: TaskService, args, json_mode: bool) -> int:
    project, task = require_task(service, args.project, args.number)
    name = args.name.strip()
    remaining = [
        (link.name, link.target) for link in task.links if link.name != name
    ]
    if len(remaining) == len(task.links):
        raise CliError(f"Link '{name}' not found", code="not_found")
    updated = service.update_task(
        task.id,  # type: ignore[arg-type]
        UpdateTaskRequest(links=remaining),
    )
    if json_mode:
        emit_json(task_payload(service, project, updated))
    return 0


def cmd_source_module_list(host: SourceHost, json_mode: bool) -> int:
    json_rows: list[dict[str, object]] = []
    table_rows: list[list[object]] = []
    for loaded in host.list_loaded():
        cfg = loaded.config
        module_id = (cfg.module_id or "").strip()
        if not module_id:
            continue
        version = cfg.installed_version
        if loaded.manifest is not None and loaded.manifest.version:
            version = loaded.manifest.version
        enabled = bool(cfg.enabled)
        is_loaded = loaded.module is not None
        error = loaded.load_error
        json_rows.append(
            {
                "id": module_id,
                "display_name": cfg.display_name,
                "enabled": enabled,
                "version": version,
                "loaded": is_loaded,
                "error": error,
            }
        )
        table_rows.append(
            [
                module_id,
                cfg.display_name,
                "true" if enabled else "false",
                version,
                "true" if is_loaded else "false",
                error or "",
            ]
        )
    emit_table(
        ["ID", "DISPLAY_NAME", "ENABLED", "VERSION", "LOADED", "ERROR"],
        table_rows,
        json_mode=json_mode,
        json_rows=json_rows,
    )
    return 0


def _optional_flag(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _source_item_address(
    service: TaskService, args
) -> tuple[str, str]:
    project_name = _optional_flag(getattr(args, "project", None))
    number = _optional_flag(getattr(args, "number", None))
    module_id = _optional_flag(getattr(args, "module", None))
    external_id = _optional_flag(getattr(args, "external_id", None))

    if (project_name is None) != (number is None):
        raise CliError("Specify both --project and --number", code="usage")
    if (module_id is None) != (external_id is None):
        raise CliError("Specify both --module and --external-id", code="usage")

    from_flags = (
        (module_id, external_id)
        if module_id is not None and external_id is not None
        else None
    )
    from_task: tuple[str, str] | None = None
    if project_name is not None and number is not None:
        _project, task = require_task(service, project_name, number)
        if not task.has_source or not task.source_module_id or not task.external_id:
            raise CliError(
                f"Task '{number}' has no source link",
                code="error",
            )
        from_task = (task.source_module_id, task.external_id)

    if from_flags is None and from_task is None:
        raise CliError(
            "Specify --module and --external-id, or --project and --number",
            code="usage",
        )
    if from_flags is not None and from_task is not None and from_flags != from_task:
        raise CliError(
            "Source item address does not match the Task source link",
            code="error",
        )
    if from_flags is not None:
        return from_flags
    assert from_task is not None
    return from_task


def cmd_task_source(
    service: TaskService, host: SourceHost, args, json_mode: bool
) -> int:
    module_id, external_id = _source_item_address(service, args)
    draft = host.get_item(module_id, external_id)
    emit_json(source_draft_payload(draft))
    return 0


def cmd_task_source_refresh(
    service: TaskService, host: SourceHost, args, json_mode: bool
) -> int:
    if _optional_flag(getattr(args, "module", None)) or _optional_flag(
        getattr(args, "external_id", None)
    ):
        raise CliError(
            "task source refresh does not accept --module or --external-id",
            code="usage",
        )
    project_name = _optional_flag(getattr(args, "project", None))
    number = _optional_flag(getattr(args, "number", None))
    if project_name is None or number is None:
        raise CliError(
            "task source refresh requires --project and --number",
            code="usage",
        )
    project, task = require_task(service, project_name, number)
    if task.id is None:
        raise CliError(
            f"Task '{number}' not found in project '{project_name}'",
            code="not_found",
        )
    updated = host.refresh_task_from_source(task.id)
    emit_json(task_payload(service, project, updated))
    return 0
