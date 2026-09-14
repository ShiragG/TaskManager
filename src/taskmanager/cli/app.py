from __future__ import annotations

import os
from argparse import Namespace
from pathlib import Path

from PySide6.QtWidgets import QApplication

from taskmanager.cli.commands import (
    CliError,
    cmd_link_add,
    cmd_link_list,
    cmd_link_remove,
    cmd_project_create,
    cmd_project_delete,
    cmd_project_list,
    cmd_project_rename,
    cmd_source_module_list,
    cmd_task_archive,
    cmd_task_comment,
    cmd_task_create,
    cmd_task_delete,
    cmd_task_excel,
    cmd_task_folder,
    cmd_task_get,
    cmd_task_hide,
    cmd_task_list,
    cmd_task_restore,
    cmd_task_search,
    cmd_task_source,
    cmd_task_source_refresh,
    cmd_task_update,
)
from taskmanager.cli.output import emit_error, emit_stdout
from taskmanager.cli.parser import CLIUsageError, build_parser, format_help_all
from taskmanager.infrastructure.logging_setup import setup_logging
from taskmanager.infrastructure import paths as app_paths
from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.services.settings_service import Settings, SettingsStore
from taskmanager.services.source_host import SourceHost
from taskmanager.services.source_protocol import SourceModuleError
from taskmanager.services.task_service import ServiceError, TaskService


def run_cli(argv: list[str]) -> int:
    json_mode, parse_argv = _extract_flag(argv, "--json")
    help_all, parse_argv = _extract_flag(parse_argv, "--help-all")
    parser = build_parser(_prog_name(parse_argv[0] if parse_argv else argv[0]))
    if help_all:
        emit_stdout(format_help_all(parser))
        return 0
    try:
        args = parser.parse_args(parse_argv[1:])
    except CLIUsageError as exc:
        return emit_error(
            str(exc),
            code="usage",
            json_mode=json_mode,
            usage=exc.usage,
            exit_code=2,
        )
    except SystemExit as exc:
        return _system_exit_code(exc)

    args.json = json_mode or bool(getattr(args, "json", False))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _qapp(parse_argv[:1] or argv[:1])

    settings_store = SettingsStore(app_paths.default_settings_path())
    settings = settings_store.load()
    setup_logging(debug=settings.debug_logging)

    work_dir = app_paths.resolve_work_dir(settings.work_dir)
    if not work_dir.is_dir():
        return emit_error(
            f"Work directory not found: {work_dir}",
            code="error",
            json_mode=args.json,
            exit_code=1,
        )

    repo = SqliteRepository(app_paths.default_db_path())
    try:
        service = TaskService(repo, settings)
        return _dispatch(service, args, repo=repo, settings=settings)
    except CliError as exc:
        exit_code = 2 if exc.code == "usage" else 1
        return emit_error(str(exc), code=exc.code, json_mode=args.json, exit_code=exit_code)
    except ServiceError as exc:
        return emit_error(str(exc), code="error", json_mode=args.json, exit_code=1)
    except SourceModuleError as exc:
        return emit_error(str(exc), code="error", json_mode=args.json, exit_code=1)
    finally:
        repo.close()


def _needs_source_host(args: Namespace) -> bool:
    if args.command == "source":
        return True
    return args.command == "task" and getattr(args, "task_action", None) == "source"


def _make_source_host(
    repo: SqliteRepository,
    settings: Settings,
    service: TaskService,
) -> SourceHost:
    return SourceHost(repo, settings, service, modules_base=app_paths.app_dir())


def _dispatch(
    service: TaskService,
    args: Namespace,
    *,
    repo: SqliteRepository,
    settings: Settings,
) -> int:
    json_mode = bool(args.json)
    command = args.command
    host: SourceHost | None = None
    if _needs_source_host(args):
        host = _make_source_host(repo, settings, service)
    if command == "project":
        action = args.project_action
        if action == "list":
            return cmd_project_list(service, json_mode)
        if action == "create":
            return cmd_project_create(service, args.name, json_mode)
        if action == "rename":
            return cmd_project_rename(service, args.project, args.name, json_mode)
        if action == "delete":
            return cmd_project_delete(service, args.project, json_mode)
    elif command == "task":
        action = args.task_action
        if action == "list":
            return cmd_task_list(
                service,
                args.project,
                hidden=bool(args.hidden),
                archived=bool(args.archive),
                json_mode=json_mode,
            )
        if action == "search":
            return cmd_task_search(
                service,
                args.query,
                archived=bool(args.archive),
                json_mode=json_mode,
            )
        if action == "get":
            return cmd_task_get(
                service,
                args.project,
                args.number,
                field=args.field,
                json_mode=json_mode,
            )
        if action == "create":
            return cmd_task_create(service, args, json_mode)
        if action == "update":
            return cmd_task_update(service, args, json_mode)
        if action == "comment":
            return cmd_task_comment(service, args, json_mode)
        if action == "archive":
            return cmd_task_archive(service, args, json_mode)
        if action == "restore":
            return cmd_task_restore(service, args, json_mode)
        if action == "hide":
            return cmd_task_hide(service, args, hidden=True, json_mode=json_mode)
        if action == "unhide":
            return cmd_task_hide(service, args, hidden=False, json_mode=json_mode)
        if action == "delete":
            return cmd_task_delete(service, args, json_mode)
        if action == "folder":
            return cmd_task_folder(service, args, json_mode)
        if action == "excel":
            return cmd_task_excel(service, args, json_mode)
        if action == "source":
            if host is None:
                return emit_error(
                    "Source host is unavailable",
                    code="error",
                    json_mode=json_mode,
                    exit_code=1,
                )
            if args.source_action == "refresh":
                return cmd_task_source_refresh(service, host, args, json_mode)
            return cmd_task_source(service, host, args, json_mode)
    elif command == "link":
        action = args.link_action
        if action == "list":
            return cmd_link_list(service, args, json_mode)
        if action == "add":
            return cmd_link_add(service, args, json_mode)
        if action == "remove":
            return cmd_link_remove(service, args, json_mode)
    elif command == "source":
        if host is None:
            return emit_error(
                "Source host is unavailable",
                code="error",
                json_mode=json_mode,
                exit_code=1,
            )
        if (
            args.source_target == "module"
            and args.source_module_action == "list"
        ):
            return cmd_source_module_list(host, json_mode)
    return emit_error("Unknown command", code="usage", json_mode=json_mode, exit_code=2)


def _extract_flag(argv: list[str], flag: str) -> tuple[bool, list[str]]:
    found = False
    kept: list[str] = []
    for index, token in enumerate(argv):
        if index > 0 and token == flag:
            found = True
            continue
        kept.append(token)
    return found, kept


def _prog_name(argv0: str) -> str:
    name = Path(argv0).name
    if name in {"__main__.py", "-c"}:
        return "taskmanager"
    return name or "taskmanager"


def _qapp(argv: list[str]) -> QApplication:
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication(argv or ["taskmanager"])


def _system_exit_code(exc: SystemExit) -> int:
    code = exc.code
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1
