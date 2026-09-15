from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from taskmanager.main import run
from taskmanager.services.settings_service import Settings, SettingsStore


@pytest.fixture
def isolated_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setattr("taskmanager.infrastructure.paths.app_dir", lambda: tmp_path)
    SettingsStore(tmp_path / "settings.json").save(
        Settings(
            work_dir=str(work),
            create_task_folder=False,
            check_updates_on_startup=False,
            check_module_updates_on_startup=False,
        )
    )
    return tmp_path


def invoke(*args: str) -> int:
    return run(["taskmanager", *args])


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert invoke("--help") == 0
    out = capsys.readouterr().out
    assert "Usage:" in out
    assert "Commands" in out
    assert "Options" in out
    assert "project" in out
    assert "task" in out
    assert "link" in out
    assert "source" in out
    assert "--help-all" in out


def test_help_all_prints_nested_usage(capsys: pytest.CaptureFixture[str]) -> None:
    assert invoke("--help-all") == 0
    out = capsys.readouterr().out
    assert out.count("Usage:") >= 4
    assert "project list" in out
    assert "task search" in out
    assert "task source" in out
    assert "source module" in out
    assert "link add" in out
    assert not out.lstrip().startswith("{")


def test_help_all_ignores_json_flag(capsys: pytest.CaptureFixture[str]) -> None:
    assert invoke("--json", "--help-all") == 0
    out = capsys.readouterr().out
    assert "Usage:" in out
    assert "task source" in out
    assert not out.lstrip().startswith("{")


def test_unknown_command_exits_two(capsys: pytest.CaptureFixture[str]) -> None:
    assert invoke("nope") == 2
    err = capsys.readouterr().err
    assert "invalid choice" in err.lower() or "unknown" in err.lower()


def test_unknown_command_json_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert invoke("--json", "nope") == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["code"] == "usage"
    assert payload["error"]


def test_no_arguments_uses_gui_not_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    gui: list[list[str]] = []
    monkeypatch.setattr(
        "taskmanager.main.run_gui",
        lambda argv: gui.append(list(argv)) or 0,
    )

    def boom(_argv: list[str]) -> int:
        raise AssertionError("CLI must not run without extra argv")

    monkeypatch.setattr("taskmanager.cli.run_cli", boom)
    assert run(["taskmanager"]) == 0
    assert gui == [["taskmanager"]]


def test_project_list_create_get_and_comment_append(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert invoke("project", "create", "--name", "Alpha") == 0
    assert capsys.readouterr().out.strip() == "Alpha"

    assert invoke("project", "list") == 0
    listed = capsys.readouterr().out
    assert "NAME" in listed
    assert "Alpha" in listed

    assert invoke(
        "task",
        "create",
        "--project",
        "Alpha",
        "--number",
        "42",
        "--description",
        "hello",
    ) == 0
    assert capsys.readouterr().out.strip() == "42"

    assert invoke("task", "list", "--project", "Alpha") == 0
    table = capsys.readouterr().out
    assert "PRIORITY" in table
    assert "42" in table
    assert "hello" in table

    assert invoke("task", "get", "--project", "Alpha", "--number", "42") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["number"] == "42"
    assert payload["project"] == "Alpha"
    assert payload["description"] == "hello"
    assert payload["description_plain"] == "hello"
    assert payload["priority"] == 10
    assert payload["folder"] is None
    assert "id" not in payload
    assert payload["links"] == []

    assert (
        invoke(
            "task",
            "comment",
            "append",
            "--project",
            "Alpha",
            "--number",
            "42",
            "--text",
            "note <ok>",
        )
        == 0
    )
    capsys.readouterr()
    assert invoke("task", "get", "--project", "Alpha", "--number", "42") == 0
    after = json.loads(capsys.readouterr().out)
    assert "<p>" in after["comment"]
    assert "note &lt;ok&gt;" in after["comment"]
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", after["comment"])
    assert "note <ok>" in after["comment_plain"]


def test_folder_null_then_ensure(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert invoke("project", "create", "--name", "Beta") == 0
    capsys.readouterr()
    assert invoke("task", "create", "--project", "Beta", "--number", "1") == 0
    capsys.readouterr()

    assert invoke("task", "get", "--project", "Beta", "--number", "1", "--field", "folder") == 0
    assert capsys.readouterr().out.strip() == "null"

    assert invoke("task", "folder", "--project", "Beta", "--number", "1") == 1
    err = capsys.readouterr().err
    assert "no folder" in err.lower()

    assert invoke("task", "folder", "ensure", "--project", "Beta", "--number", "1") == 0
    path = Path(capsys.readouterr().out.strip())
    assert path.is_dir()

    assert invoke("task", "get", "--project", "Beta", "--number", "1") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["folder"] == str(path)
    assert payload["has_folder"] is True


def test_cli_runs_while_instance_lock_held(
    isolated_app: Path, qtbot, capsys: pytest.CaptureFixture[str]
) -> None:
    from taskmanager.infrastructure.single_instance import InstanceGuard

    guard = InstanceGuard(isolated_app)
    assert guard.try_become_primary()
    try:
        assert invoke("project", "list") == 0
        out = capsys.readouterr().out
        assert "NAME" in out
    finally:
        guard.release()


def test_hide_archive_restore_delete(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invoke("project", "create", "--name", "Gamma")
    invoke("task", "create", "--project", "Gamma", "--number", "7")
    capsys.readouterr()

    assert invoke("task", "hide", "--project", "Gamma", "--number", "7") == 0
    assert invoke("task", "list", "--project", "Gamma") == 0
    assert "7" not in _task_numbers(capsys.readouterr().out)
    assert invoke("task", "list", "--project", "Gamma", "--hidden") == 0
    assert "7" in _task_numbers(capsys.readouterr().out)

    assert invoke("task", "unhide", "--project", "Gamma", "--number", "7") == 0
    assert invoke("task", "archive", "--project", "Gamma", "--number", "7") == 0
    assert invoke("task", "list", "--project", "Gamma") == 0
    assert "7" not in _task_numbers(capsys.readouterr().out)
    assert invoke("task", "list", "--project", "Gamma", "--archive") == 0
    assert "7" in _task_numbers(capsys.readouterr().out)

    assert invoke("task", "restore", "--project", "Gamma", "--number", "7") == 0
    assert invoke("task", "delete", "--project", "Gamma", "--number", "7") == 0
    assert invoke("task", "get", "--project", "Gamma", "--number", "7") == 1
    assert "not found" in capsys.readouterr().err.lower()


def _task_numbers(table: str) -> list[str]:
    lines = [line for line in table.splitlines() if line.strip()]
    numbers: list[str] = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 2:
            numbers.append(parts[1])
    return numbers


def test_task_search_table_has_project_column(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invoke("project", "create", "--name", "Alpha")
    invoke("project", "create", "--name", "Beta")
    invoke(
        "task",
        "create",
        "--project",
        "Alpha",
        "--number",
        "10",
        "--description",
        "needle in alpha",
    )
    invoke(
        "task",
        "create",
        "--project",
        "Beta",
        "--number",
        "20",
        "--description",
        "other",
    )
    capsys.readouterr()

    assert invoke("task", "search", "needle") == 0
    table = capsys.readouterr().out
    assert "PROJECT" in table
    assert "Alpha" in table
    assert "10" in table
    assert "needle in alpha" in table
    assert "Beta" not in table
    assert "20" not in table

    assert invoke("--json", "task", "search", "needle") == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows == [
        {
            "project": "Alpha",
            "priority": 10,
            "number": "10",
            "status": "Новая",
            "date_end": None,
            "description_plain": "needle in alpha",
            "comment_plain": "",
        }
    ]


def test_task_search_archive_excludes_active(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invoke("project", "create", "--name", "Gamma")
    invoke(
        "task",
        "create",
        "--project",
        "Gamma",
        "--number",
        "7",
        "--description",
        "archived needle",
    )
    invoke("task", "archive", "--project", "Gamma", "--number", "7")
    capsys.readouterr()

    assert invoke("task", "search", "needle") == 0
    active = capsys.readouterr().out
    assert "7" not in active

    assert invoke("task", "search", "needle", "--archive") == 0
    archived = capsys.readouterr().out
    assert "PROJECT" in archived
    assert "Gamma" in archived
    assert "7" in archived


def test_task_search_without_query_is_usage(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert invoke("task", "search") == 2
    capsys.readouterr()


def test_hidden_and_archive_flags_are_exclusive(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invoke("project", "create", "--name", "Delta")
    capsys.readouterr()
    assert invoke("task", "list", "--project", "Delta", "--hidden", "--archive") == 2
    assert capsys.readouterr().err


def test_links_and_excel(isolated_app: Path, capsys: pytest.CaptureFixture[str]) -> None:
    invoke("project", "create", "--name", "Epsilon")
    invoke("task", "create", "--project", "Epsilon", "--number", "1")
    capsys.readouterr()

    assert (
        invoke(
            "link",
            "add",
            "--project",
            "Epsilon",
            "--number",
            "1",
            "--name",
            "docs",
            "--target",
            "https://example.com",
        )
        == 0
    )
    assert invoke("link", "list", "--project", "Epsilon", "--number", "1") == 0
    listed = capsys.readouterr().out
    assert "docs" in listed
    assert "https://example.com" in listed

    dest = isolated_app / "out.xlsx"
    dest.write_bytes(b"old")
    assert invoke("task", "excel", "--project", "Epsilon", "--output", str(dest)) == 0
    capsys.readouterr()
    assert dest.is_file()
    assert dest.stat().st_size > 4

    assert invoke("link", "remove", "--project", "Epsilon", "--number", "1", "--name", "docs") == 0
    assert invoke("--json", "link", "list", "--project", "Epsilon", "--number", "1") == 0
    assert json.loads(capsys.readouterr().out) == []


def test_json_not_found_error(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert invoke("--json", "task", "get", "--project", "Missing", "--number", "1") == 1
    payload = json.loads(capsys.readouterr().err)
    assert payload["code"] == "not_found"
    assert payload["error"]


def test_cannot_delete_project_with_active_tasks(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invoke("project", "create", "--name", "Busy")
    invoke("task", "create", "--project", "Busy", "--number", "1")
    capsys.readouterr()
    assert invoke("project", "delete", "--project", "Busy") == 1
    err = capsys.readouterr().err.lower()
    assert "активн" in err or "active" in err


def test_comment_set_replaces_field(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invoke("project", "create", "--name", "Notes")
    invoke("task", "create", "--project", "Notes", "--number", "1", "--comment", "old")
    capsys.readouterr()
    assert (
        invoke(
            "task",
            "comment",
            "set",
            "--project",
            "Notes",
            "--number",
            "1",
            "--text",
            "new only",
        )
        == 0
    )
    capsys.readouterr()
    invoke("task", "get", "--project", "Notes", "--number", "1")
    payload = json.loads(capsys.readouterr().out)
    assert payload["comment"] == "new only"
    assert "old" not in payload["comment"]


def test_update_renames_number(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invoke("project", "create", "--name", "Rename")
    invoke("task", "create", "--project", "Rename", "--number", "10")
    capsys.readouterr()
    assert (
        invoke(
            "task",
            "update",
            "--project",
            "Rename",
            "--number",
            "10",
            "--new-number",
            "20",
            "--status",
            "in_progress",
        )
        == 0
    )
    capsys.readouterr()
    assert invoke("task", "get", "--project", "Rename", "--number", "20") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["workflow_status"] == "in_progress"
    assert invoke("task", "get", "--project", "Rename", "--number", "10") == 1


def test_spec_is_console_build() -> None:
    spec = Path(__file__).resolve().parents[1] / "TaskManager.spec"
    text = spec.read_text(encoding="utf-8")
    assert "console=True" in text


def test_hide_console_noop_when_not_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    from taskmanager.cli import console

    monkeypatch.setattr(console.sys, "platform", "linux")

    def boom() -> object:
        raise AssertionError("Windows console APIs must not run on Linux")

    monkeypatch.setattr(console, "_windows_kernel32", boom)
    monkeypatch.setattr(console, "_windows_user32", boom)
    console.hide_console_if_only_ours()


def test_hide_console_noop_without_console_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from taskmanager.cli import console

    monkeypatch.setattr(console.sys, "platform", "win32")

    class Kernel:
        def GetConsoleWindow(self) -> int:
            return 0

        def GetConsoleProcessList(self, processes, count: int) -> int:
            raise AssertionError("must not query processes without a window")

    class User:
        def ShowWindow(self, hwnd: int, cmd: int) -> int:
            raise AssertionError("must not hide without a console window")

    monkeypatch.setattr(console, "_windows_kernel32", lambda: Kernel())
    monkeypatch.setattr(console, "_windows_user32", lambda: User())
    console.hide_console_if_only_ours()


def test_hide_console_hides_exclusive_window(monkeypatch: pytest.MonkeyPatch) -> None:
    from taskmanager.cli import console

    monkeypatch.setattr(console.sys, "platform", "win32")

    class Kernel:
        def GetConsoleWindow(self) -> int:
            return 0xABC

        def GetConsoleProcessList(self, processes, count: int) -> int:
            processes[0] = 1234
            return 1

        def ShowWindow(self, hwnd: int, cmd: int) -> int:
            raise AssertionError("ShowWindow lives in user32, not kernel32")

    shown: list[tuple[int, int]] = []

    class User:
        def ShowWindow(self, hwnd: int, cmd: int) -> int:
            shown.append((hwnd, cmd))
            return 1

    monkeypatch.setattr(console, "_windows_kernel32", lambda: Kernel())
    monkeypatch.setattr(console, "_windows_user32", lambda: User())
    console.hide_console_if_only_ours()
    assert shown == [(0xABC, console.SW_HIDE)]


def test_hide_console_keeps_shared_window(monkeypatch: pytest.MonkeyPatch) -> None:
    from taskmanager.cli import console

    monkeypatch.setattr(console.sys, "platform", "win32")

    class Kernel:
        def GetConsoleWindow(self) -> int:
            return 0xABC

        def GetConsoleProcessList(self, processes, count: int) -> int:
            processes[0] = 1234
            processes[1] = 5678
            return 2

    class User:
        def ShowWindow(self, hwnd: int, cmd: int) -> int:
            raise AssertionError("must not hide a shared console")

    monkeypatch.setattr(console, "_windows_kernel32", lambda: Kernel())
    monkeypatch.setattr(console, "_windows_user32", lambda: User())
    console.hide_console_if_only_ours()


def test_normalize_text_keeps_inner_blank_lines() -> None:
    from taskmanager.cli.output import normalize_text

    assert normalize_text("a  \n\nb\n\n") == "a\n\nb"
    assert normalize_text("a\n") == "a"
    assert normalize_text("\n\n") == ""


def test_help_with_json_flag_stays_argparse_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert invoke("--json", "--help") == 0
    out = capsys.readouterr().out
    assert "Usage:" in out
    assert not out.lstrip().startswith("{")


def test_cli_commands_do_not_touch_service_repo() -> None:
    text = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "taskmanager"
        / "cli"
        / "commands.py"
    ).read_text(encoding="utf-8")
    assert "service.repo" not in text


def test_readme_lists_cli_commands_and_help_caveat() -> None:
    text = Path(__file__).resolve().parents[1].joinpath("README.md").read_text(
        encoding="utf-8"
    )
    for fragment in (
        "project rename",
        "project delete",
        "task search",
        "task update",
        "task comment set",
        "task archive",
        "task restore",
        "task hide",
        "task unhide",
        "task delete",
        "task folder",
        "task excel",
        "link list",
        "link add",
        "link remove",
        "source module list",
        "task source",
        "task source refresh",
        "--help-all",
        "--module",
        "--external-id",
        "--help",
        "--json",
    ):
        assert fragment in text
    assert "argparse" in text


def test_source_host_not_built_for_task_list(
    isolated_app: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    invoke("project", "create", "--name", "P")
    capsys.readouterr()

    def boom(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("SourceHost must not be created")

    monkeypatch.setattr("taskmanager.cli.app._make_source_host", boom)
    assert invoke("task", "list", "--project", "P") == 0
    assert invoke("task", "search", "nothing") == 0
    assert invoke("project", "list") == 0


def test_source_help_uses_source_module_wording(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert invoke("source", "--help") == 0
    out = capsys.readouterr().out.lower()
    assert "source module" in out
    assert "plugin" not in out
    assert invoke("task", "source", "--help") == 0
    task_out = capsys.readouterr().out.lower()
    assert "source item" in task_out or "source" in task_out
    assert "plugin" not in task_out


def test_source_module_list_table_and_json(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from taskmanager.infrastructure.paths import default_db_path
    from taskmanager.infrastructure.sqlite_repo import SqliteRepository

    repo = SqliteRepository(default_db_path())
    try:
        repo.upsert_source_module(
            module_id="fake",
            display_name="Fake Module",
            enabled=True,
            installed_version="1.2.3",
        )
    finally:
        repo.close()

    assert invoke("source", "module", "list") == 0
    table = capsys.readouterr().out
    assert "ID" in table
    assert "fake" in table
    assert "Fake Module" in table
    for line in table.splitlines():
        assert line == line.rstrip()
    assert not table.endswith("\n\n")

    assert invoke("--json", "source", "module", "list") == 0
    rows = json.loads(capsys.readouterr().out)
    by_id = {row["id"]: row for row in rows}
    fake = by_id["fake"]
    assert fake["display_name"] == "Fake Module"
    assert fake["enabled"] is True
    assert fake["version"] == "1.2.3"
    assert fake["loaded"] is False
    assert "github_repo" not in fake
    assert "password" not in fake


def _seed_linked_task(isolated_app: Path, *, comment: str = "<b>keep me</b>") -> None:
    from taskmanager.infrastructure.paths import default_db_path
    from taskmanager.infrastructure.sqlite_repo import SqliteRepository
    from taskmanager.services.settings_service import SettingsStore
    from taskmanager.services.task_service import CreateTaskRequest, TaskService

    repo = SqliteRepository(default_db_path())
    try:
        repo.upsert_source_module(
            module_id="fake", enabled=True, display_name="Fake"
        )
        service = TaskService(repo, SettingsStore(isolated_app / "settings.json").load())
        project = service.create_project("Src")
        service.create_task(
            CreateTaskRequest(
                project_id=project.id,  # type: ignore[arg-type]
                number="9",
                description="old",
                comment=comment,
                create_folder=False,
                source_module_id="fake",
                external_id="ext-9",
                source_label="Fake",
                source_status_id="10",
                source_status_label="Старое",
            )
        )
    finally:
        repo.close()


def test_task_source_by_module_calls_get_item_without_project(
    isolated_app: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from taskmanager.services.source_host import SourceHost
    from taskmanager.services.source_protocol import SourceDraft, SourceFileMeta

    draft = SourceDraft(
        external_id="ext-9",
        number="9",
        description="live from source",
        priority=3,
        links=[("Razr", "https://example/9")],
        files=[SourceFileMeta(file_id="f1", name="a.pdf")],
        source_label="Fake",
        source_status_id="3",
        source_status_label="В работе",
    )
    calls: list[tuple[str, str]] = []

    def fake_host(repo, settings, service):
        host = SourceHost(repo, settings, service, modules_base=isolated_app)

        def get_item(module_id: str, external_id: str):
            calls.append((module_id, external_id))
            return draft

        host.get_item = get_item  # type: ignore[method-assign]
        return host

    monkeypatch.setattr("taskmanager.cli.app._make_source_host", fake_host)
    assert (
        invoke("task", "source", "--module", "fake", "--external-id", "ext-9") == 0
    )
    assert calls == [("fake", "ext-9")]
    payload = json.loads(capsys.readouterr().out)
    assert payload["external_id"] == "ext-9"
    assert payload["description"] == "live from source"
    assert payload["description_plain"] == "live from source"
    assert payload["files"] == [{"file_id": "f1", "name": "a.pdf"}]
    assert payload["links"] == [{"name": "Razr", "target": "https://example/9"}]


def test_task_source_without_address_is_usage(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert invoke("task", "source") == 2
    capsys.readouterr()


def test_task_source_refresh_without_project_is_usage(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert invoke("task", "source", "refresh") == 2
    err = capsys.readouterr().err.lower()
    assert "project" in err or "usage" in err or "required" in err


def test_task_source_refresh_rejects_module_flags(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invoke("project", "create", "--name", "Src")
    invoke("task", "create", "--project", "Src", "--number", "9")
    capsys.readouterr()
    assert (
        invoke(
            "task",
            "source",
            "refresh",
            "--project",
            "Src",
            "--number",
            "9",
            "--module",
            "fake",
            "--external-id",
            "ext-9",
        )
        == 2
    )
    capsys.readouterr()


def test_task_source_without_link_exits_one(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invoke("project", "create", "--name", "Alpha")
    invoke("task", "create", "--project", "Alpha", "--number", "1")
    capsys.readouterr()
    assert invoke("task", "source", "--project", "Alpha", "--number", "1") == 1
    err = capsys.readouterr().err.lower()
    assert "source" in err or "источник" in err


def test_task_source_returns_live_draft_json(
    isolated_app: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from taskmanager.services.source_host import SourceHost
    from taskmanager.services.source_protocol import SourceDraft, SourceFileMeta

    _seed_linked_task(isolated_app)
    draft = SourceDraft(
        external_id="ext-9",
        number="9",
        description="live from source",
        priority=3,
        links=[("Razr", "https://example/9")],
        files=[SourceFileMeta(file_id="f1", name="a.pdf")],
        source_label="Fake",
        source_status_id="3",
        source_status_label="В работе",
    )

    def fake_host(repo, settings, service):
        host = SourceHost(repo, settings, service, modules_base=isolated_app)
        host.get_item = lambda _mid, _eid: draft  # type: ignore[method-assign]
        return host

    monkeypatch.setattr("taskmanager.cli.app._make_source_host", fake_host)
    assert invoke("task", "source", "--project", "Src", "--number", "9") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["external_id"] == "ext-9"
    assert payload["description"] == "live from source"
    assert payload["description_plain"] == "live from source"
    assert payload["files"] == [{"file_id": "f1", "name": "a.pdf"}]
    assert payload["links"] == [{"name": "Razr", "target": "https://example/9"}]

    assert invoke("task", "get", "--project", "Src", "--number", "9") == 0
    stored = json.loads(capsys.readouterr().out)
    assert stored["description"] == "old"


def test_task_source_diverging_addresses_exit_one(
    isolated_app: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from taskmanager.services.source_host import SourceHost
    from taskmanager.services.source_protocol import SourceDraft

    _seed_linked_task(isolated_app)

    def fake_host(repo, settings, service):
        host = SourceHost(repo, settings, service, modules_base=isolated_app)
        host.get_item = lambda _mid, _eid: SourceDraft(  # type: ignore[method-assign]
            external_id="other",
            number="9",
            description="should not run",
        )
        return host

    monkeypatch.setattr("taskmanager.cli.app._make_source_host", fake_host)
    assert (
        invoke(
            "task",
            "source",
            "--project",
            "Src",
            "--number",
            "9",
            "--module",
            "other",
            "--external-id",
            "ext-other",
        )
        == 1
    )
    err = capsys.readouterr().err.lower()
    assert "match" in err or "diverg" in err or "source" in err


def test_task_source_refresh_keeps_comment(
    isolated_app: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import dataclass

    from taskmanager.services.settings_service import SourceModuleConfig
    from taskmanager.services.source_host import LoadedSource, SourceHost
    from taskmanager.services.source_protocol import SourceDraft, SourceListPage

    @dataclass
    class FakeModule:
        id: str = "fake"
        display_name: str = "Fake"
        version: str = "0.0.1"
        api_version: str = "1"
        draft: SourceDraft | None = None

        def configure(self, *, login: str, password: str) -> None:
            return None

        def list_statuses(self):
            return []

        def list_priorities(self):
            return []

        def list_items(self, page: int = 1, status_filters=None) -> SourceListPage:
            return SourceListPage(items=[], page=page)

        def get_item(self, external_id: str) -> SourceDraft:
            assert self.draft is not None
            return self.draft

        def download_files(self, external_id, dest_dir, existing_names=None):
            return []

    _seed_linked_task(isolated_app, comment="<b>keep me</b>")
    draft = SourceDraft(
        external_id="ext-9",
        number="9",
        description="from source",
        priority=0,
        links=[],
        files=[],
        source_label="Fake",
        source_status_id="3",
        source_status_label="В работе",
    )

    def fake_host(repo, settings, service):
        host = SourceHost(repo, settings, service, modules_base=isolated_app)
        host._by_id["fake"] = LoadedSource(
            config=SourceModuleConfig(
                module_id="fake", enabled=True, display_name="Fake"
            ),
            manifest=None,
            module=FakeModule(draft=draft),
            load_error=None,
        )
        monkeypatch.setattr(host, "get_credentials", lambda _mid: ("u", "p"))
        return host

    monkeypatch.setattr("taskmanager.cli.app._make_source_host", fake_host)
    assert invoke("task", "source", "refresh", "--project", "Src", "--number", "9") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["comment"] == "<b>keep me</b>"
    assert "from source" in payload["description"]
    assert payload["priority"] == 0
    assert payload["source_status_label"] == "В работе"


def test_task_list_status_is_display_status(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invoke("project", "create", "--name", "W")
    invoke(
        "task",
        "create",
        "--project",
        "W",
        "--number",
        "1",
        "--status",
        "in_progress",
    )
    capsys.readouterr()
    assert invoke("task", "list", "--project", "W") == 0
    table = capsys.readouterr().out
    assert "В работе" in table
    for line in table.splitlines():
        assert line == line.rstrip()
    assert not table.endswith("\n\n")

    assert invoke("--json", "task", "list", "--project", "W") == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["status"] == "В работе"

    assert invoke("task", "get", "--project", "W", "--number", "1") == 0
    got = json.loads(capsys.readouterr().out)
    assert got["status"] == "active"
    assert got["workflow_status"] == "in_progress"

    invoke("task", "archive", "--project", "W", "--number", "1")
    capsys.readouterr()
    assert invoke("--json", "task", "list", "--project", "W", "--archive") == 0
    archived = json.loads(capsys.readouterr().out)
    assert archived[0]["status"] == "В работе"


def test_json_comment_keeps_inner_blank_lines(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invoke("project", "create", "--name", "T")
    invoke(
        "task",
        "create",
        "--project",
        "T",
        "--number",
        "1",
        "--comment",
        "para1\n\npara2\n\n",
    )
    capsys.readouterr()
    assert invoke("task", "get", "--project", "T", "--number", "1") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["comment"] == "para1\n\npara2"


def test_unknown_workflow_status_is_usage(
    isolated_app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invoke("project", "create", "--name", "T")
    capsys.readouterr()
    assert invoke("task", "create", "--project", "T", "--status", "archived") == 2
    assert capsys.readouterr().err
