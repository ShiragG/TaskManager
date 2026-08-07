from pathlib import Path

from taskmanager.services.settings_service import (
    THEME_SYSTEM,
    Settings,
    SettingsStore,
)
from taskmanager.services.update_service import (
    ReleaseAsset,
    LatestRelease,
    asset_name_for_platform,
    parse_release_payload,
    parse_version,
    pick_asset,
    staged_update_path,
    version_is_newer,
    write_restart_helper,
)


def test_parse_version():
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("0.1.0") == (0, 1, 0)
    assert parse_version("v2") == (2, 0, 0)


def test_version_is_newer():
    assert version_is_newer("v0.2.0", "0.1.0")
    assert not version_is_newer("v0.1.0", "0.1.0")
    assert not version_is_newer("v0.0.9", "0.1.0")
    # Patch releases must be detected (0.6.0 → 0.6.1).
    assert version_is_newer("v0.6.1", "0.6.0")
    assert version_is_newer("0.6.1", "0.6.0")
    assert not version_is_newer("v0.6.0", "0.6.1")
    assert not version_is_newer("0.6.1", "0.6.1")


def test_update_service_is_newer_patch():
    from taskmanager.services.update_service import UpdateService

    svc = UpdateService()
    assert svc.is_newer("v0.6.1", "0.6.0")
    assert not svc.is_newer("v0.6.0", "0.6.1")
    assert not svc.is_newer("not-a-version", "0.6.0")


def test_asset_name_for_platform():
    assert asset_name_for_platform("Linux") == "TaskManager"
    assert asset_name_for_platform("Windows") == "TaskManager.exe"
    assert asset_name_for_platform("win32") == "TaskManager.exe"


def test_staged_update_path(tmp_path: Path):
    path = staged_update_path(system="Linux", directory=tmp_path)
    assert path == tmp_path / "TaskManager.new"
    win = staged_update_path(system="Windows", directory=tmp_path)
    assert win == tmp_path / "TaskManager.exe.new"


def test_write_restart_helper_unix(tmp_path: Path):
    new_path = tmp_path / "TaskManager.new"
    target = tmp_path / "TaskManager"
    new_path.write_bytes(b"x")
    helper = write_restart_helper(
        new_path=new_path, target_path=target, pid=12345, helper_dir=tmp_path
    )
    assert helper.is_file()
    text = helper.read_text(encoding="utf-8")
    assert "12345" in text
    assert str(new_path) in text
    assert "taskmanager_update.log" in text
    assert "taskmanager_update.crash.log" in text
    assert "setsid" in text or "nohup" in text
    assert "ATTEMPT" in text
    assert "relaunch OK" in text
    assert "relaunch FAIL" in text
    assert "kill -0" in text
    assert "2>>\"$CRASH\"" in text or "2>>$CRASH" in text
    assert helper.stat().st_mode & 0o111


def test_write_restart_helper_windows_content(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "taskmanager.services.update_service.platform.system",
        lambda: "Windows",
    )
    new_path = tmp_path / "TaskManager.exe.new"
    target = tmp_path / "TaskManager.exe"
    new_path.write_bytes(b"x")
    helper = write_restart_helper(
        new_path=new_path, target_path=target, pid=999, helper_dir=tmp_path
    )
    assert helper.name.endswith(".bat")
    text = helper.read_text(encoding="utf-8")
    assert "taskmanager_update.log" in text
    assert "timeout /t 2" in text
    assert "ATTEMPT" in text
    assert "chcp 65001" in text
    assert f'start "" /D "{tmp_path}"' in text or 'start "" /D "%APPDIR%"' in text
    assert "relaunch OK" in text
    assert "relaunch FAIL" in text
    assert "IMAGENAME eq TaskManager.exe" in text


def test_launch_restart_helper_windows_uses_cmd(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "taskmanager.services.update_service.platform.system",
        lambda: "Windows",
    )
    calls: list[tuple] = []

    class FakePopen:
        def __init__(self, args, **kwargs):
            calls.append((list(args), kwargs))

    monkeypatch.setattr(
        "subprocess.Popen",
        FakePopen,
    )
    helper = tmp_path / "taskmanager_apply_update.bat"
    helper.write_text("@echo off\n", encoding="utf-8")
    from taskmanager.services.update_service import (
        _CREATE_NEW_CONSOLE,
        launch_restart_helper,
    )

    launch_restart_helper(helper)
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0].lower().endswith("cmd.exe") or args[0] == "cmd.exe"
    assert args[1] == "/c"
    assert args[2] == str(helper)
    # CREATE_NEW_CONSOLE only — DETACHED_PROCESS causes WinError 87.
    assert kwargs.get("creationflags") == _CREATE_NEW_CONSOLE
    assert kwargs.get("creationflags") == 0x00000010


def test_parse_release_and_pick_asset():
    payload = {
        "tag_name": "v1.4.0",
        "assets": [
            {
                "name": "TaskManager",
                "browser_download_url": "https://example.com/TaskManager",
                "size": 10,
            },
            {
                "name": "TaskManager.exe",
                "browser_download_url": "https://example.com/TaskManager.exe",
                "size": 11,
            },
        ],
    }
    release = parse_release_payload(payload)
    assert release.tag == "v1.4.0"
    assert release.version == "1.4.0"
    linux = pick_asset(release.assets, "TaskManager")
    assert linux is not None
    assert linux.download_url.endswith("/TaskManager")
    win = pick_asset(release.assets, "TaskManager.exe")
    assert win is not None
    assert isinstance(win, ReleaseAsset)


def test_latest_release_dataclass():
    release = LatestRelease(
        tag="v1.0.0",
        version="1.0.0",
        assets=[ReleaseAsset("TaskManager", "https://x/y", 1)],
    )
    assert release.assets[0].name == "TaskManager"


def test_settings_theme_default(tmp_path: Path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = Settings(work_dir=str(tmp_path / "work"))
    store.save(settings)
    loaded = store.load()
    assert loaded.theme_mode == THEME_SYSTEM
    assert loaded.create_task_folder is True
