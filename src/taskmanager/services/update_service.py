from __future__ import annotations

import json
import logging
import platform
import re
import stat
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from taskmanager.infrastructure.paths import app_dir


GITHUB_LATEST_URL = (
    "https://api.github.com/repos/ShiragG/TaskManager/releases/latest"
)
USER_AGENT = "TaskManager-UpdateCheck"

logger = logging.getLogger(__name__)


class UpdateError(Exception):
    """Failed to check or download an update."""


class UpdateCancelled(UpdateError):
    """Download was cancelled by the user."""


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    download_url: str
    size: int | None = None


@dataclass(frozen=True)
class LatestRelease:
    tag: str
    version: str
    assets: list[ReleaseAsset]


ProgressCallback = Callable[[int, int | None, float], None]
CancelPredicate = Callable[[], bool]


_VERSION_RE = re.compile(
    r"^v?(?P<major>\d+)(?:\.(?P<minor>\d+))?(?:\.(?P<patch>\d+))?",
    re.IGNORECASE,
)


def parse_version(tag_or_version: str) -> tuple[int, int, int]:
    """Parse ``vX.Y.Z`` / ``X.Y.Z`` into a comparable triple."""
    text = tag_or_version.strip()
    match = _VERSION_RE.match(text)
    if not match:
        raise UpdateError(f"Не удалось разобрать версию: {tag_or_version!r}")
    major = int(match.group("major"))
    minor = int(match.group("minor") or 0)
    patch = int(match.group("patch") or 0)
    return major, minor, patch


def version_is_newer(remote: str, current: str) -> bool:
    return parse_version(remote) > parse_version(current)


def asset_name_for_platform(system: str | None = None) -> str:
    name = (system or platform.system()).lower()
    if name.startswith("win"):
        return "TaskManager.exe"
    return "TaskManager"


def staged_update_path(*, system: str | None = None, directory: Path | None = None) -> Path:
    """Path for the downloaded binary: ``TaskManager[.exe].new`` beside the app."""
    base = directory or app_dir()
    return base / f"{asset_name_for_platform(system)}.new"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def current_executable() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve()
    return Path(sys.argv[0]).resolve()


def pick_asset(
    assets: list[ReleaseAsset], asset_name: str
) -> ReleaseAsset | None:
    for asset in assets:
        if asset.name == asset_name:
            return asset
    return None


def parse_release_payload(payload: dict[str, Any]) -> LatestRelease:
    tag = str(payload.get("tag_name") or "").strip()
    if not tag:
        raise UpdateError("В ответе GitHub нет tag_name")
    version = tag[1:] if tag.lower().startswith("v") else tag
    assets: list[ReleaseAsset] = []
    for raw in payload.get("assets") or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "")
        url = str(raw.get("browser_download_url") or "")
        if not name or not url:
            continue
        size_raw = raw.get("size")
        size = int(size_raw) if isinstance(size_raw, int) else None
        assets.append(ReleaseAsset(name=name, download_url=url, size=size))
    return LatestRelease(tag=tag, version=version, assets=assets)


UPDATE_LOG_NAME = "taskmanager_update.log"


def update_log_path(*, directory: Path | None = None) -> Path:
    """Path for the restart-helper log (next to the app / staged update)."""
    base = directory or app_dir()
    return base / UPDATE_LOG_NAME


def write_restart_helper(
    *,
    new_path: Path,
    target_path: Path,
    pid: int,
    helper_dir: Path | None = None,
) -> Path:
    """Write a platform helper that replaces ``target_path`` with ``new_path`` after PID exits."""
    directory = helper_dir or new_path.parent
    directory.mkdir(parents=True, exist_ok=True)
    log_path = update_log_path(directory=directory)
    is_windows = platform.system().lower().startswith("win")
    if is_windows:
        helper = directory / "taskmanager_apply_update.bat"
        old_path = target_path.with_suffix(target_path.suffix + ".old")
        app_dir_win = str(target_path.parent)
        target_name = target_path.name
        # cmd /c launches this .bat; log every step for frozen diagnose.
        # UTF-8 code page avoids OEM mojibake if tools write to the console;
        # do not redirect move/del stdout into the log (OEM text).
        content = f"""@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >NUL
set "PID={pid}"
set "NEW={new_path}"
set "TARGET={target_path}"
set "OLD={old_path}"
set "APPDIR={app_dir_win}"
set "LOG={log_path}"
echo [%date% %time%] helper start pid=%PID% > "%LOG%"
echo NEW=%NEW%>> "%LOG%"
echo TARGET=%TARGET%>> "%LOG%"
echo APPDIR=%APPDIR%>> "%LOG%"
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
  echo [%date% %time%] FAILED to move NEW to TARGET; leaving .new in place>> "%LOG%"
  if exist "%OLD%" move /y "%OLD%" "%TARGET%" >NUL 2>&1
  exit /b 1
)
echo [%date% %time%] starting new binary>> "%LOG%"
start "" /D "%APPDIR%" "%TARGET%"
timeout /t 2 /nobreak >NUL
tasklist /FI "IMAGENAME eq {target_name}" 2>NUL | find /I "{target_name}" >NUL
if errorlevel 1 (
  echo [%date% %time%] relaunch FAIL - {target_name} not running; start manually from %TARGET%>> "%LOG%"
) else (
  echo [%date% %time%] relaunch OK - {target_name} is running>> "%LOG%"
)
if exist "%OLD%" del /f /q "%OLD%" >NUL 2>&1
echo [%date% %time%] helper done>> "%LOG%"
del /f /q "%~f0"
"""
        helper.write_text(content, encoding="utf-8", newline="\r\n")
        logger.info("Wrote Windows update helper %s (log=%s)", helper, log_path)
        return helper

    helper = directory / "taskmanager_apply_update.sh"
    old_path = Path(str(target_path) + ".old")
    crash_log = directory / "taskmanager_update.crash.log"
    # Quote paths; retry mv on ETXTBSY/busy; log to taskmanager_update.log.
    # New binary stderr goes to .crash.log (not /dev/null) so launch crashes are visible.
    content = f"""#!/bin/sh
set -eu
PID={pid}
NEW="{new_path}"
TARGET="{target_path}"
OLD="{old_path}"
LOG="{log_path}"
CRASH="{crash_log}"
log() {{
  echo "$(date -Iseconds 2>/dev/null || date) $*" >> "$LOG"
}}
log "helper start pid=$PID"
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
  log "FAILED to move NEW to TARGET; leaving .new in place"
  exit 1
done
chmod +x "$TARGET" || true
log "starting new binary"
# Detach from this helper's session so the new app outlives the script.
# Keep stderr so a crash is not swallowed into /dev/null.
: > "$CRASH"
if command -v setsid >/dev/null 2>&1; then
  setsid "$TARGET" </dev/null >/dev/null 2>>"$CRASH" &
else
  nohup "$TARGET" </dev/null >/dev/null 2>>"$CRASH" &
fi
NEWPID=$!
sleep 2
if kill -0 "$NEWPID" 2>/dev/null; then
  log "relaunch OK pid=$NEWPID"
else
  log "relaunch FAIL pid=$NEWPID (process not alive); see $CRASH; start manually: $TARGET"
fi
rm -f "$OLD" || true
log "helper done"
rm -f -- "$0"
"""
    helper.write_text(content, encoding="utf-8")
    mode = helper.stat().st_mode
    helper.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    logger.info("Wrote Unix update helper %s (log=%s)", helper, log_path)
    return helper


# CREATE_NEW_CONSOLE — must not combine with DETACHED_PROCESS (WinError 87).
_CREATE_NEW_CONSOLE = 0x00000010


def launch_restart_helper(helper: Path) -> None:
    """Start the apply-update helper detached, then caller should exit.

    On Windows, ``.bat`` must be launched via ``cmd.exe /c`` — ``Popen([bat])``
    often fails to start the script at all. Use only ``CREATE_NEW_CONSOLE``
    (not ``DETACHED_PROCESS``) so CreateProcess succeeds.
    """
    import subprocess

    helper = Path(helper)
    is_windows = platform.system().lower().startswith("win")
    if is_windows:
        cmd = os_environ_comspec()
        popen_args = [cmd, "/c", str(helper)]
        logger.info("Launching Windows update helper via %s /c %s", cmd, helper)
        subprocess.Popen(  # noqa: S603
            popen_args,
            cwd=str(helper.parent),
            creationflags=_CREATE_NEW_CONSOLE,
            close_fds=True,
        )
        return

    logger.info("Launching Unix update helper %s", helper)
    subprocess.Popen(  # noqa: S603
        ["/bin/sh", str(helper)],
        cwd=str(helper.parent),
        start_new_session=True,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def os_environ_comspec() -> str:
    """Resolve ``cmd.exe`` for Windows helper launch."""
    import os

    return os.environ.get("COMSPEC") or "cmd.exe"


class UpdateService:
    """Check GitHub Releases and download the platform binary."""

    def __init__(
        self,
        *,
        api_url: str = GITHUB_LATEST_URL,
        opener: Any | None = None,
    ) -> None:
        self.api_url = api_url
        self._opener = opener

    def fetch_latest_release(self) -> LatestRelease:
        raw = self._http_get_json(self.api_url)
        if not isinstance(raw, dict):
            raise UpdateError("Некорректный ответ GitHub API")
        release = parse_release_payload(raw)
        logger.debug(
            "Fetched latest release tag=%s assets=%d",
            release.tag,
            len(release.assets),
        )
        return release

    def is_newer(self, remote_tag: str, current_version: str) -> bool:
        try:
            return version_is_newer(remote_tag, current_version)
        except UpdateError:
            return False

    def find_asset(
        self, release: LatestRelease, asset_name: str | None = None
    ) -> ReleaseAsset | None:
        name = asset_name or asset_name_for_platform()
        return pick_asset(release.assets, name)

    def download_asset(
        self,
        asset: ReleaseAsset,
        dest: Path,
        *,
        progress_callback: ProgressCallback | None = None,
        should_cancel: CancelPredicate | None = None,
        chunk_size: int = 64 * 1024,
    ) -> Path:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(
            asset.download_url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"},
        )
        cancelled = False
        try:
            if self._opener is not None:
                response_cm = self._opener.open(request)
            else:
                response_cm = urllib.request.urlopen(request, timeout=120)
            with response_cm as resp, dest.open("wb") as out:
                total = asset.size
                if total is None:
                    length = resp.headers.get("Content-Length")
                    if length and length.isdigit():
                        total = int(length)
                bytes_done = 0
                started = time.monotonic()
                last_report = started
                while True:
                    if should_cancel is not None and should_cancel():
                        cancelled = True
                        break
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out.write(chunk)
                    bytes_done += len(chunk)
                    now = time.monotonic()
                    if progress_callback is not None and (
                        now - last_report >= 0.1 or (total and bytes_done >= total)
                    ):
                        elapsed = max(now - started, 1e-6)
                        speed = bytes_done / elapsed
                        progress_callback(bytes_done, total, speed)
                        last_report = now
        except UpdateCancelled:
            raise
        except urllib.error.URLError as exc:
            logger.exception("Update download failed")
            self._cleanup_partial(dest)
            raise UpdateError(f"Не удалось скачать обновление: {exc}") from exc
        except OSError as exc:
            logger.exception("Update save failed")
            self._cleanup_partial(dest)
            raise UpdateError(f"Не удалось сохранить файл: {exc}") from exc

        if cancelled:
            self._cleanup_partial(dest)
            logger.info("Update download cancelled, removed partial file %s", dest)
            raise UpdateCancelled("Загрузка отменена")
        # Ensure executable bit on Unix downloads
        if not platform.system().lower().startswith("win"):
            try:
                mode = dest.stat().st_mode
                dest.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            except OSError:
                logger.exception("Failed to chmod downloaded update")
        logger.info("Update downloaded to %s (%s bytes)", dest, dest.stat().st_size)
        return dest

    @staticmethod
    def _cleanup_partial(dest: Path) -> None:
        try:
            if dest.is_file():
                dest.unlink()
        except OSError:
            logger.exception("Failed to remove partial update file: %s", dest)

    def _http_get_json(self, url: str) -> Any:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/vnd.github+json",
            },
        )
        try:
            if self._opener is not None:
                with self._opener.open(request) as resp:
                    body = resp.read()
            else:
                with urllib.request.urlopen(request, timeout=30) as resp:
                    body = resp.read()
        except urllib.error.HTTPError as exc:
            logger.exception("GitHub API HTTP error")
            raise UpdateError(f"GitHub API: HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            logger.exception("GitHub API network error")
            raise UpdateError(f"Нет сети или GitHub недоступен: {exc}") from exc
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.exception("GitHub API JSON parse error")
            raise UpdateError("Некорректный JSON от GitHub") from exc
