from __future__ import annotations

import argparse

from taskmanager.domain import WorkflowStatus


class CLIUsageError(Exception):
    """argparse usage failure (exit 2)."""

    def __init__(self, message: str, usage: str = "") -> None:
        super().__init__(message)
        self.usage = usage


class GnuHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """GNU-style headings: Usage / Commands / Options."""

    def add_usage(self, usage, actions, groups, prefix=None):
        if prefix is None:
            prefix = "Usage: "
        return super().add_usage(usage, actions, groups, prefix)

    def start_section(self, heading: str | None) -> None:
        mapping = {
            "positional arguments": "Commands",
            "optional arguments": "Options",
            "options": "Options",
        }
        if heading in mapping:
            heading = mapping[heading]
        super().start_section(heading)


class CliParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CLIUsageError(message, usage=self.format_usage())


def _ident_parser() -> argparse.ArgumentParser:
    ident = argparse.ArgumentParser(add_help=False)
    ident.add_argument("--project", required=True, help="Project name")
    ident.add_argument("--number", required=True, help="Task number")
    return ident


def build_parser(prog: str) -> CliParser:
    parser = CliParser(
        prog=prog,
        description="Manage projects, tasks, and links from the command line.",
        formatter_class=GnuHelpFormatter,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON instead of a table or plain text",
    )
    parser.add_argument(
        "--help-all",
        action="store_true",
        help="Print help for every command and exit",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    project_p = sub.add_parser(
        "project",
        help="Project commands",
        formatter_class=GnuHelpFormatter,
    )
    project_sub = project_p.add_subparsers(
        dest="project_action", required=True, metavar="command"
    )
    project_sub.add_parser("list", help="List projects", formatter_class=GnuHelpFormatter)
    create_proj = project_sub.add_parser(
        "create", help="Create a project", formatter_class=GnuHelpFormatter
    )
    create_proj.add_argument("--name", required=True, help="Project name")
    rename_proj = project_sub.add_parser(
        "rename", help="Rename a project", formatter_class=GnuHelpFormatter
    )
    rename_proj.add_argument("--project", required=True, help="Current project name")
    rename_proj.add_argument("--name", required=True, help="New project name")
    delete_proj = project_sub.add_parser(
        "delete", help="Delete a project", formatter_class=GnuHelpFormatter
    )
    delete_proj.add_argument("--project", required=True, help="Project name")

    task_p = sub.add_parser(
        "task",
        help="Task commands",
        formatter_class=GnuHelpFormatter,
    )
    task_sub = task_p.add_subparsers(
        dest="task_action", required=True, metavar="command"
    )

    ident = _ident_parser()
    status_choices = tuple(status.value for status in WorkflowStatus)

    list_t = task_sub.add_parser(
        "list", help="List tasks in a project", formatter_class=GnuHelpFormatter
    )
    list_t.add_argument("--project", required=True, help="Project name")
    list_mode = list_t.add_mutually_exclusive_group()
    list_mode.add_argument(
        "--hidden",
        action="store_true",
        help="List hidden active tasks instead of the default view",
    )
    list_mode.add_argument(
        "--archive",
        action="store_true",
        help="List archived tasks instead of the default view",
    )

    search_t = task_sub.add_parser(
        "search",
        help="Search tasks across projects",
        formatter_class=GnuHelpFormatter,
    )
    search_t.add_argument(
        "query",
        metavar="QUERY",
        help="Match number, description, or comment (all projects)",
    )
    search_t.add_argument(
        "--archive",
        action="store_true",
        help="Search archived tasks instead of the default view",
    )

    get_t = task_sub.add_parser(
        "get",
        help="Print one task as JSON",
        formatter_class=GnuHelpFormatter,
        parents=[ident],
    )
    get_t.add_argument(
        "--field",
        metavar="KEY",
        help="Print the JSON value of a single key",
    )

    create_t = task_sub.add_parser(
        "create", help="Create a task", formatter_class=GnuHelpFormatter
    )
    create_t.add_argument("--project", required=True, help="Project name")
    create_t.add_argument("--number", help="Task number (default: next proposed)")
    create_t.add_argument("--description", default=None, help="Description")
    create_t.add_argument("--comment", default=None, help="Comment")
    create_t.add_argument("--priority", type=int, default=None, help="Priority 0..10")
    create_t.add_argument(
        "--status",
        choices=status_choices,
        default=None,
        help="Workflow status",
    )
    create_t.add_argument(
        "--date-end",
        metavar="YYYY-MM-DD",
        dest="date_end",
        default=None,
        help="Due date",
    )
    create_t.add_argument("--hidden", action="store_true", help="Create as hidden")
    create_t.add_argument(
        "--folder",
        action="store_true",
        help="Create an on-disk folder for the task",
    )

    update_t = task_sub.add_parser(
        "update",
        help="Update a task",
        formatter_class=GnuHelpFormatter,
        parents=[ident],
    )
    update_t.add_argument(
        "--new-number",
        dest="new_number",
        default=None,
        help="New task number (renames the folder when one exists)",
    )
    update_t.add_argument("--description", default=None, help="Description")
    update_t.add_argument("--comment", default=None, help="Comment")
    update_t.add_argument("--priority", type=int, default=None, help="Priority 0..10")
    update_t.add_argument(
        "--status",
        choices=status_choices,
        default=None,
        help="Workflow status",
    )
    update_t.add_argument(
        "--date-end",
        metavar="YYYY-MM-DD",
        dest="date_end",
        default=None,
        help="Due date",
    )

    comment_t = task_sub.add_parser(
        "comment",
        help="Replace or append the comment",
        formatter_class=GnuHelpFormatter,
        parents=[ident],
    )
    comment_t.add_argument(
        "comment_action",
        choices=("set", "append"),
        help="set replaces the field; append adds a dated plain-text block",
    )
    comment_t.add_argument("--text", required=True, help="Comment text")

    for action, help_text in (
        ("archive", "Archive a task"),
        ("restore", "Restore an archived task"),
        ("hide", "Hide a task"),
        ("unhide", "Unhide a task"),
        ("delete", "Delete a task"),
    ):
        task_sub.add_parser(
            action,
            help=help_text,
            formatter_class=GnuHelpFormatter,
            parents=[ident],
        )

    folder_t = task_sub.add_parser(
        "folder",
        help="Print the task folder path, or create it with 'ensure'",
        formatter_class=GnuHelpFormatter,
        parents=[ident],
    )
    folder_t.add_argument(
        "folder_action",
        nargs="?",
        choices=("ensure",),
        help="Create the folder if it is missing",
    )

    excel_t = task_sub.add_parser(
        "excel",
        help="Export a project to an .xlsx file",
        formatter_class=GnuHelpFormatter,
    )
    excel_t.add_argument("--project", required=True, help="Project name")
    excel_t.add_argument(
        "--output",
        required=True,
        metavar="PATH.xlsx",
        help="Destination workbook (overwritten if it exists)",
    )

    source_t = task_sub.add_parser(
        "source",
        help="Print the live Source item as JSON, or refresh the Task from it",
        formatter_class=GnuHelpFormatter,
        description=(
            "Read a live Source item without writing the Task. "
            "Address the Source item with --module and --external-id, "
            "or take those ids from a Task with --project and --number."
        ),
    )
    source_t.add_argument(
        "source_action",
        nargs="?",
        choices=("refresh",),
        help=(
            "Overwrite mapped Task fields from the Source item "
            "(Comment is kept). Requires --project and --number"
        ),
    )
    source_t.add_argument("--project", help="Project name (Task address)")
    source_t.add_argument("--number", help="Task number (Task address)")
    source_t.add_argument(
        "--module",
        metavar="ID",
        help="Source module id",
    )
    source_t.add_argument(
        "--external-id",
        dest="external_id",
        metavar="X",
        help="Source item external id",
    )

    link_p = sub.add_parser(
        "link",
        help="Link commands",
        formatter_class=GnuHelpFormatter,
    )
    link_sub = link_p.add_subparsers(
        dest="link_action", required=True, metavar="command"
    )
    link_sub.add_parser(
        "list",
        help="List links on a task",
        formatter_class=GnuHelpFormatter,
        parents=[ident],
    )
    add_link = link_sub.add_parser(
        "add",
        help="Add a link",
        formatter_class=GnuHelpFormatter,
        parents=[ident],
    )
    add_link.add_argument("--name", required=True, help="Link name")
    add_link.add_argument("--target", required=True, help="URL or filesystem path")
    remove_link = link_sub.add_parser(
        "remove",
        help="Remove a link by name",
        formatter_class=GnuHelpFormatter,
        parents=[ident],
    )
    remove_link.add_argument("--name", required=True, help="Link name")

    source_p = sub.add_parser(
        "source",
        help="Source module commands",
        formatter_class=GnuHelpFormatter,
    )
    source_sub = source_p.add_subparsers(
        dest="source_target", required=True, metavar="command"
    )
    module_p = source_sub.add_parser(
        "module",
        help="Source module registry",
        formatter_class=GnuHelpFormatter,
    )
    module_sub = module_p.add_subparsers(
        dest="source_module_action", required=True, metavar="command"
    )
    module_sub.add_parser(
        "list",
        help="List Source modules in the registry",
        formatter_class=GnuHelpFormatter,
    )

    return parser


def format_help_all(parser: argparse.ArgumentParser) -> str:
    seen: set[int] = set()
    chunks: list[str] = []

    def walk(node: argparse.ArgumentParser) -> None:
        ident = id(node)
        if ident in seen:
            return
        seen.add(ident)
        chunks.append(node.format_help().rstrip())
        for action in node._actions:
            if isinstance(action, argparse._SubParsersAction):
                for child in action.choices.values():
                    walk(child)

    walk(parser)
    return "\n\n".join(chunks)
