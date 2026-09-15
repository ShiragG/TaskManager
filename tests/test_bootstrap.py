from __future__ import annotations

import io
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from taskmanager.bootstrap import (
    ONEDIR_DIST_NAME,
    PAYLOAD_ZIP_NAME,
    BootstrapError,
    extract_onedir_payload,
    loader_temp_path,
    main as bootstrap_main,
    render_bootstrap_spec,
    write_bootstrap_helper,
    write_onedir_payload_zip,
)


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_extract_writes_loader_to_temp_and_internal(tmp_path: Path):
    payload = tmp_path / "payload.zip"
    payload.write_bytes(
        _zip_bytes(
            {
                "TaskManager": b"loader-bytes",
                "_internal/lib.txt": b"qt",
            }
        )
    )
    dest = tmp_path / "app"
    dest.mkdir()
    loader = extract_onedir_payload(
        payload, dest, loader_name="TaskManager"
    )
    assert loader == dest / "TaskManager.onedir-new"
    assert loader.read_bytes() == b"loader-bytes"
    assert (dest / "_internal" / "lib.txt").read_bytes() == b"qt"
    assert not (dest / "TaskManager").exists()


def test_extract_does_not_touch_settings_db_or_modules(tmp_path: Path):
    dest = tmp_path / "app"
    dest.mkdir()
    (dest / "settings.json").write_text('{"keep": true}', encoding="utf-8")
    (dest / "taskmanager.db").write_bytes(b"sqlite")
    modules = dest / "modules"
    modules.mkdir()
    (modules / "razr.zip").write_bytes(b"plugin")

    payload = tmp_path / "payload.zip"
    payload.write_bytes(
        _zip_bytes(
            {
                "TaskManager": b"new-loader",
                "_internal/a.txt": b"ok",
                "settings.json": b"from-zip",
                "taskmanager.db": b"from-zip-db",
                "modules/evil.zip": b"nope",
                "modules/nested/x.txt": b"nope",
            }
        )
    )
    extract_onedir_payload(payload, dest, loader_name="TaskManager")
    assert (dest / "settings.json").read_text(encoding="utf-8") == '{"keep": true}'
    assert (dest / "taskmanager.db").read_bytes() == b"sqlite"
    assert (modules / "razr.zip").read_bytes() == b"plugin"
    assert not (modules / "evil.zip").exists()
    assert not (modules / "nested").exists()
    assert (dest / "_internal" / "a.txt").read_bytes() == b"ok"


def test_extract_rejects_zip_slip(tmp_path: Path):
    payload = tmp_path / "payload.zip"
    payload.write_bytes(
        _zip_bytes(
            {
                "TaskManager": b"loader",
                "../outside.txt": b"bad",
                "_internal/../outside2.txt": b"bad",
            }
        )
    )
    dest = tmp_path / "app"
    dest.mkdir()
    extract_onedir_payload(payload, dest, loader_name="TaskManager")
    assert not (tmp_path / "outside.txt").exists()
    assert not (dest / "outside2.txt").exists()
    assert (dest / "TaskManager.onedir-new").is_file()


def test_extract_requires_loader(tmp_path: Path):
    payload = tmp_path / "payload.zip"
    payload.write_bytes(_zip_bytes({"_internal/a.txt": b"x"}))
    with pytest.raises(BootstrapError, match="loader"):
        extract_onedir_payload(
            payload, tmp_path / "app", loader_name="TaskManager"
        )


def test_loader_temp_path_keeps_exe_suffix():
    dest = Path("/app")
    assert loader_temp_path(dest, "TaskManager.exe") == dest / "TaskManager.exe.onedir-new"
    assert loader_temp_path(dest, "TaskManager") == dest / "TaskManager.onedir-new"


def test_write_onedir_payload_zip_requires_loader(tmp_path: Path):
    onedir = tmp_path / ONEDIR_DIST_NAME
    (onedir / "_internal").mkdir(parents=True)
    (onedir / "_internal" / "lib.so").write_bytes(b"so")
    with pytest.raises(BootstrapError, match="loader"):
        write_onedir_payload_zip(onedir, tmp_path / PAYLOAD_ZIP_NAME)


def test_write_onedir_payload_zip(tmp_path: Path):
    onedir = tmp_path / ONEDIR_DIST_NAME
    (onedir / "_internal").mkdir(parents=True)
    (onedir / "TaskManager").write_bytes(b"exe")
    (onedir / "_internal" / "lib.so").write_bytes(b"so")
    (onedir / "settings.json").write_text("should-not-ship", encoding="utf-8")
    zip_path = tmp_path / PAYLOAD_ZIP_NAME
    write_onedir_payload_zip(onedir, zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    assert "TaskManager" in names
    assert "_internal/lib.so" in names
    assert "settings.json" not in names


def test_bootstrap_helper_unix_replaces_and_relaunches(tmp_path: Path):
    target = tmp_path / "TaskManager"
    new_path = tmp_path / "TaskManager.onedir-new"
    target.write_bytes(b"old-bootstrap")
    new_path.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$(dirname \"$0\")/ran.txt\"\n",
        encoding="utf-8",
    )
    new_path.chmod(new_path.stat().st_mode | stat.S_IXUSR)
    helper = write_bootstrap_helper(
        new_path=new_path,
        target_path=target,
        pid=999999,
        argv=["--help", "search"],
        helper_dir=tmp_path,
    )
    text = helper.read_text(encoding="utf-8")
    assert "999999" in text
    assert "exec" in text
    assert "--help" in text
    completed = subprocess.run(
        ["/bin/sh", str(helper)],
        cwd=tmp_path,
        check=False,
        timeout=20,
    )
    assert completed.returncode == 0
    assert target.read_text(encoding="utf-8").startswith("#!/bin/sh")
    assert not new_path.exists()
    ran = (tmp_path / "ran.txt").read_text(encoding="utf-8").splitlines()
    assert ran == ["--help", "search"]


def test_write_bootstrap_helper_windows_relaunches(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "taskmanager.bootstrap.platform.system",
        lambda: "Windows",
    )
    new_path = tmp_path / "TaskManager.exe.onedir-new"
    target = tmp_path / "TaskManager.exe"
    new_path.write_bytes(b"x")
    helper = write_bootstrap_helper(
        new_path=new_path,
        target_path=target,
        pid=42,
        argv=["--help"],
        helper_dir=tmp_path,
    )
    assert helper.name.endswith(".bat")
    text = helper.read_text(encoding="utf-8")
    assert "42" in text
    assert "taskmanager_update.log" in text
    assert 'start ""' in text
    assert "--help" in text
    assert "start the app manually" not in text


def test_render_bootstrap_spec_is_onefile(tmp_path: Path):
    payload = tmp_path / PAYLOAD_ZIP_NAME
    payload.write_bytes(b"zip")
    spec = render_bootstrap_spec(
        payload_zip=payload,
        entry=Path("src/taskmanager/bootstrap_main.py"),
        icon=Path("src/taskmanager/resources/app_icon.ico"),
    )
    assert "COLLECT" not in spec
    assert "console=True" in spec
    assert "TaskManager" in spec
    assert PAYLOAD_ZIP_NAME in spec
    assert "PySide6" in spec
    assert "bootstrap_main.py" in spec


def test_main_unpacks_and_launches_helper(tmp_path: Path, monkeypatch):
    dest = tmp_path / "install"
    dest.mkdir()
    (dest / "TaskManager").write_bytes(b"bootstrap")
    payload = tmp_path / PAYLOAD_ZIP_NAME
    payload.write_bytes(
        _zip_bytes({"TaskManager": b"loader", "_internal/a.txt": b"x"})
    )
    launched: list[Path] = []
    monkeypatch.setattr(
        "taskmanager.bootstrap.bundled_payload_path", lambda: payload
    )
    monkeypatch.setattr("taskmanager.bootstrap._install_dir", lambda: dest)
    monkeypatch.setattr(
        "taskmanager.bootstrap.default_loader_name", lambda **_: "TaskManager"
    )
    monkeypatch.setattr(
        "taskmanager.bootstrap.launch_bootstrap_helper", launched.append
    )
    monkeypatch.setattr("taskmanager.bootstrap.os.getpid", lambda: 321)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(dest / "TaskManager"))
    assert bootstrap_main(["TaskManager", "--help"]) == 0
    assert (dest / "TaskManager.onedir-new").read_bytes() == b"loader"
    assert (dest / "_internal" / "a.txt").read_bytes() == b"x"
    assert len(launched) == 1
    helper_text = launched[0].read_text(encoding="utf-8")
    assert "321" in helper_text
    assert "--help" in helper_text


def test_main_missing_payload_exits_1(monkeypatch, capsys):
    def boom() -> Path:
        raise BootstrapError("Missing payload onedir-payload.zip")

    monkeypatch.setattr("taskmanager.bootstrap.bundled_payload_path", boom)
    assert bootstrap_main(["TaskManager"]) == 1
    assert "Missing payload" in capsys.readouterr().err


def test_taskmanager_spec_is_onedir():
    spec = Path(__file__).resolve().parents[1].joinpath("TaskManager.spec")
    text = spec.read_text(encoding="utf-8")
    assert "COLLECT(" in text
    assert "exclude_binaries=True" in text
    assert "contents_directory='_internal'" in text
    assert ONEDIR_DIST_NAME in text
    assert "console=True" in text
    assert "runtime_tmpdir" not in text
