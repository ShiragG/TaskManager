from __future__ import annotations

import os
import platform
import subprocess
import webbrowser
from pathlib import Path


class PlatformOpenError(Exception):
    """Raised when a link or path cannot be opened."""


def open_target(target: str) -> None:
    """Open a URL, directory, or file with the system default handler."""
    if target.startswith(("http://", "https://")):
        webbrowser.open(target)
        return

    path = Path(target)
    if path.is_dir():
        _open_directory(path)
        return
    if path.is_file():
        _open_file(path)
        return

    raise PlatformOpenError(f"Не удаётся открыть ссылку: {target}")


def _open_directory(path: Path) -> None:
    system = platform.system()
    if system == "Windows":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def _open_file(path: Path) -> None:
    system = platform.system()
    if system == "Windows":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
