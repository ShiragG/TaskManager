from __future__ import annotations

import os
import platform
import subprocess
import sys
import webbrowser
from pathlib import Path


class PlatformOpenError(Exception):
    """Raised when a link or path cannot be opened."""


def open_target(target: str) -> None:
    """Open a URL, directory, or file with the system default handler."""
    if target.startswith(("http://", "https://")):
        webbrowser.open(target)
        return

    path = Path(target).expanduser()
    try:
        path = path.resolve(strict=False)
    except OSError as exc:
        raise PlatformOpenError(f"Не удаётся открыть ссылку: {target}") from exc

    if path.is_dir():
        _open_path(path)
        return
    if path.is_file():
        _open_path(path)
        return

    raise PlatformOpenError(f"Не удаётся открыть ссылку: {target}")


def _open_env() -> dict[str, str]:
    """Env for child processes; strip PyInstaller/Qt paths that break xdg-open."""
    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        for key in (
            "LD_LIBRARY_PATH",
            "QT_PLUGIN_PATH",
            "QML2_IMPORT_PATH",
            "PYTHONHOME",
            "PYTHONPATH",
        ):
            env.pop(key, None)
    return env


def _open_path(path: Path) -> None:
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)], start_new_session=True)
        else:
            subprocess.Popen(
                ["xdg-open", str(path)],
                env=_open_env(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
    except OSError as exc:
        raise PlatformOpenError(f"Не удаётся открыть: {path}\n{exc}") from exc
