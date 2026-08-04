import sys
from pathlib import Path

from taskmanager.infrastructure.filesystem import TaskFilesystem
from taskmanager.infrastructure.paths import resolve_work_dir
from taskmanager.infrastructure.platform_open import PlatformOpenError, open_target
from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.services.settings_service import Settings
from taskmanager.services.task_service import CreateTaskRequest, TaskService


def test_resolve_work_dir_relative_to_app_dir(monkeypatch, tmp_path: Path):
    install = tmp_path / "install"
    other = tmp_path / "other"
    install.mkdir()
    other.mkdir()
    exe = install / "TaskManager"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.chdir(other)

    resolved = resolve_work_dir("Working directory")
    assert resolved == (install / "Working directory").resolve()
    assert resolve_work_dir("/abs/work") == Path("/abs/work")


def test_task_folder_openable_when_cwd_differs_from_app_dir(
    monkeypatch, tmp_path: Path
):
    install = tmp_path / "install"
    other = tmp_path / "other"
    install.mkdir()
    other.mkdir()
    exe = install / "TaskManager"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))

    monkeypatch.chdir(install)
    settings = Settings(work_dir="Working directory")
    repo = SqliteRepository(install / "tm.db")
    svc = TaskService(repo, settings, TaskFilesystem(settings))
    directory = svc.create_directory("Alpha")
    task = svc.create_task(
        CreateTaskRequest(directory_id=directory.id, number="7", description="x")
    )
    expected = install / "Working directory" / "Alpha" / "7"
    assert expected.is_dir()

    monkeypatch.chdir(other)
    path = svc.task_folder_path(task.id)
    assert path.is_dir()
    assert path.resolve() == expected.resolve()

    launched: list[str] = []

    def fake_popen(cmd, *args, **kwargs):
        launched.append(cmd[1])

        class _Proc:
            pass

        return _Proc()

    monkeypatch.setattr(
        "taskmanager.infrastructure.platform_open.subprocess.Popen",
        fake_popen,
    )
    open_target(str(path))
    assert Path(launched[0]).resolve() == expected.resolve()
    repo.close()


def test_open_target_missing_path_raises():
    try:
        open_target(str(Path("/no/such/taskmanager/folder/xyz")))
        raise AssertionError("expected PlatformOpenError")
    except PlatformOpenError:
        pass
