from __future__ import annotations

"""GitHub-asset bootstrap: unpack onedir beside the exe, then replace+relaunch."""

import os
import platform
import shlex
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path


PAYLOAD_ZIP_NAME = "onedir-payload.zip"
ONEDIR_DIST_NAME = "TaskManager-onedir"
LOADER_TEMP_SUFFIX = ".onedir-new"
UPDATE_LOG_NAME = "taskmanager_update.log"
PROTECTED_ROOT_NAMES = frozenset(
    {
        "settings.json",
        "taskmanager.db",
        "modules",
    }
)

_CREATE_NEW_CONSOLE = 0x00000010


class BootstrapError(Exception):
    """Bootstrap payload is missing, unsafe, or could not be applied."""


def default_loader_name(*, system: str | None = None) -> str:
    name = (system or platform.system()).lower()
    if name.startswith("win"):
        return "TaskManager.exe"
    return "TaskManager"


def loader_temp_path(dest: Path, loader_name: str) -> Path:
    return dest / f"{loader_name}{LOADER_TEMP_SUFFIX}"


def bundled_payload_path() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and meipass:
        path = Path(meipass) / PAYLOAD_ZIP_NAME
        if path.is_file():
            return path
    raise BootstrapError(f"Missing payload {PAYLOAD_ZIP_NAME}")


def write_onedir_payload_zip(onedir: Path, zip_path: Path) -> Path:
    """Zip onedir contents for the bootstrap payload; skip user-data names."""
    onedir = Path(onedir)
    if not onedir.is_dir():
        raise BootstrapError(f"Onedir directory not found: {onedir}")
    if not (onedir / "TaskManager").is_file() and not (
        onedir / "TaskManager.exe"
    ).is_file():
        raise BootstrapError(f"Onedir has no TaskManager loader: {onedir}")
    zip_path = Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(onedir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(onedir)
            if _is_protected_rel(rel):
                continue
            zf.write(path, rel.as_posix())
    return zip_path


def extract_onedir_payload(
    payload: Path,
    dest: Path,
    *,
    loader_name: str,
) -> Path:
    """Extract onedir zip into ``dest``.

    The onedir loader is written to a temporary name so a running bootstrap
    exe is not overwritten. ``settings.json``, ``taskmanager.db``, and
    ``modules/`` are never replaced.
    """
    payload = Path(payload)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    if not zipfile.is_zipfile(payload):
        raise BootstrapError(f"Payload is not a zip: {payload}")
    loader_tmp = loader_temp_path(dest, loader_name)
    wrote_loader = False
    with zipfile.ZipFile(payload) as zf:
        if _find_loader_member(zf.namelist(), loader_name) is None:
            raise BootstrapError(f"Payload zip has no onedir loader {loader_name!r}")
        for info in zf.infolist():
            member = _normalize_member(info.filename)
            if not member or member.endswith("/"):
                continue
            if _unsafe_member(member) or _is_protected_member(member):
                continue
            if _is_loader_member(member, loader_name):
                out = loader_tmp
                wrote_loader = True
            else:
                out = dest / member
            out.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, out.open("wb") as fh:
                shutil.copyfileobj(src, fh)
            _apply_zip_mode(info, out)
    if not wrote_loader:
        raise BootstrapError(f"Payload zip has no onedir loader {loader_name!r}")
    if not platform.system().lower().startswith("win"):
        mode = loader_tmp.stat().st_mode
        loader_tmp.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return loader_tmp


def write_bootstrap_helper(
    *,
    new_path: Path,
    target_path: Path,
    pid: int,
    argv: list[str] | None = None,
    helper_dir: Path | None = None,
) -> Path:
    """Write a helper that replaces the bootstrap exe and relaunches with argv."""
    argv = list(argv or [])
    directory = helper_dir or new_path.parent
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / UPDATE_LOG_NAME
    is_windows = platform.system().lower().startswith("win")
    if is_windows:
        helper = directory / "taskmanager_apply_onedir.bat"
        old_path = target_path.with_suffix(target_path.suffix + ".old")
        relaunch = _windows_relaunch_cmd(argv)
        content = f"""@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >NUL
set "PID={pid}"
set "NEW={new_path}"
set "TARGET={target_path}"
set "OLD={old_path}"
set "LOG={log_path}"
echo [%date% %time%] onedir helper start pid=%PID% > "%LOG%"
echo NEW=%NEW%>> "%LOG%"
echo TARGET=%TARGET%>> "%LOG%"
:wait
tasklist /FI "PID eq %PID%" 2>NUL | find "%PID%" >NUL
if not errorlevel 1 (
  echo [%date% %time%] waiting for pid %PID%>> "%LOG%"
  timeout /t 1 /nobreak >NUL
  goto wait
)
echo [%date% %time%] pid exited, pausing for file unlock>> "%LOG%"
timeout /t 2 /nobreak >NUL
set /a ATTEMPT=0
:replace
set /a ATTEMPT+=1
echo [%date% %time%] replace attempt !ATTEMPT!>> "%LOG%"
if exist "%OLD%" del /f /q "%OLD%" >NUL 2>&1
if exist "%TARGET%" (
  move /y "%TARGET%" "%OLD%" >NUL 2>&1
  if errorlevel 1 (
    if !ATTEMPT! LSS 15 (
      timeout /t 1 /nobreak >NUL
      goto replace
    )
    echo [%date% %time%] FAILED to move TARGET to OLD>> "%LOG%"
    exit /b 1
  )
)
move /y "%NEW%" "%TARGET%" >NUL 2>&1
if errorlevel 1 (
  if !ATTEMPT! LSS 15 (
    timeout /t 1 /nobreak >NUL
    goto replace
  )
  echo [%date% %time%] FAILED to move NEW to TARGET; leaving loader in place>> "%LOG%"
  if exist "%OLD%" move /y "%OLD%" "%TARGET%" >NUL 2>&1
  exit /b 1
)
if exist "%OLD%" del /f /q "%OLD%" >NUL 2>&1
echo [%date% %time%] replace OK; relaunch %TARGET%>> "%LOG%"
{relaunch}
echo [%date% %time%] helper done>> "%LOG%"
del /f /q "%~f0"
"""
        helper.write_text(content, encoding="utf-8", newline="\r\n")
        return helper

    helper = directory / "taskmanager_apply_onedir.sh"
    old_path = Path(str(target_path) + ".old")
    relaunch_args = " ".join(shlex.quote(a) for a in argv)
    exec_line = (
        f'exec "$TARGET" {relaunch_args}' if relaunch_args else 'exec "$TARGET"'
    )
    content = f"""#!/bin/sh
set -eu
PID={pid}
NEW="{new_path}"
TARGET="{target_path}"
OLD="{old_path}"
LOG="{log_path}"
log() {{
  echo "$(date -Iseconds 2>/dev/null || date) $*" >> "$LOG"
}}
log "onedir helper start pid=$PID"
log "NEW=$NEW"
log "TARGET=$TARGET"
while kill -0 "$PID" 2>/dev/null; do
  log "waiting for pid $PID"
  sleep 1
done
log "pid exited, pausing for file unlock"
sleep 2
ATTEMPT=0
while true; do
  ATTEMPT=$((ATTEMPT + 1))
  log "replace attempt $ATTEMPT"
  rm -f "$OLD" || true
  if [ -e "$TARGET" ]; then
    if ! mv -f "$TARGET" "$OLD" 2>>"$LOG"; then
      if [ "$ATTEMPT" -lt 15 ]; then
        sleep 1
        continue
      fi
      log "FAILED to move TARGET to OLD"
      exit 1
    fi
  fi
  if mv -f "$NEW" "$TARGET" 2>>"$LOG"; then
    break
  fi
  if [ -e "$OLD" ]; then
    mv -f "$OLD" "$TARGET" 2>>"$LOG" || true
  fi
  if [ "$ATTEMPT" -lt 15 ]; then
    sleep 1
    continue
  fi
  log "FAILED to move NEW to TARGET; leaving loader in place"
  exit 1
done
chmod +x "$TARGET" || true
rm -f "$OLD" || true
log "replace OK; relaunch $TARGET"
rm -f -- "$0"
{exec_line}
log "FAILED to relaunch $TARGET"
exit 1
"""
    helper.write_text(content, encoding="utf-8")
    mode = helper.stat().st_mode
    helper.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return helper


def launch_bootstrap_helper(helper: Path) -> None:
    """Start the onedir apply helper so it outlives this process."""
    helper = Path(helper)
    is_windows = platform.system().lower().startswith("win")
    if is_windows:
        cmd = os.environ.get("COMSPEC") or "cmd.exe"
        subprocess.Popen(  # noqa: S603
            [cmd, "/c", str(helper)],
            cwd=str(helper.parent),
            creationflags=_CREATE_NEW_CONSOLE,
            close_fds=True,
        )
        return
    subprocess.Popen(  # noqa: S603
        ["/bin/sh", str(helper)],
        cwd=str(helper.parent),
        start_new_session=True,
        close_fds=True,
    )


def render_bootstrap_spec(
    *,
    payload_zip: Path,
    entry: Path,
    icon: Path,
) -> str:
    """PyInstaller onefile spec that embeds the onedir zip (no Qt)."""
    payload = Path(payload_zip).resolve().as_posix()
    entry_s = Path(entry).as_posix()
    icon_s = Path(icon).as_posix()
    return f"""# -*- mode: python ; coding: utf-8 -*-
# Generated by scripts/package_github_asset.py — do not commit.

a = Analysis(
    [{entry_s!r}],
    pathex=[],
    binaries=[],
    datas=[({payload!r}, '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['PySide6', 'PyQt6', 'PyQt5', 'tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TaskManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[{icon_s!r}],
)
"""


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    try:
        dest = _install_dir()
        payload = bundled_payload_path()
        loader_name = default_loader_name()
        temp_loader = extract_onedir_payload(
            payload, dest, loader_name=loader_name
        )
        target = (
            Path(sys.executable).resolve()
            if getattr(sys, "frozen", False)
            else dest / loader_name
        )
        helper = write_bootstrap_helper(
            new_path=temp_loader,
            target_path=target,
            pid=os.getpid(),
            argv=argv[1:],
        )
        launch_bootstrap_helper(helper)
        return 0
    except BootstrapError as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def _normalize_member(name: str) -> str:
    normalized = name.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _unsafe_member(member: str) -> bool:
    if member.startswith("/") or member.startswith("../"):
        return True
    if "/../" in f"/{member}/":
        return True
    rel = Path(member)
    return rel.is_absolute() or ".." in rel.parts


def _is_protected_member(member: str) -> bool:
    parts = Path(member).parts
    return bool(parts) and parts[0] in PROTECTED_ROOT_NAMES


def _is_protected_rel(rel: Path) -> bool:
    parts = rel.parts
    return bool(parts) and parts[0] in PROTECTED_ROOT_NAMES


def _is_loader_member(member: str, loader_name: str) -> bool:
    return Path(member).parts == (loader_name,)


def _find_loader_member(names: list[str], loader_name: str) -> str | None:
    for name in names:
        member = _normalize_member(name)
        if _is_loader_member(member, loader_name):
            return name
    return None


def _apply_zip_mode(info: zipfile.ZipInfo, dest: Path) -> None:
    if platform.system().lower().startswith("win"):
        return
    mode = info.external_attr >> 16
    if mode:
        dest.chmod(mode & 0o777)


def _windows_relaunch_cmd(argv: list[str]) -> str:
    extra = subprocess.list2cmdline(argv)
    if extra:
        return f'start "" "%TARGET%" {extra}'
    return 'start "" "%TARGET%"'
