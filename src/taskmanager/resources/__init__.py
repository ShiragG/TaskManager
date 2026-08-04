from __future__ import annotations

import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    """Resolve a path under package resources (source tree or PyInstaller)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS) / "taskmanager" / "resources"
        candidate = base.joinpath(*parts)
        if candidate.is_file():
            return candidate
        # onefile may also unpack flat add-data layouts
        flat = Path(sys._MEIPASS).joinpath(*parts)
        if flat.is_file():
            return flat
    return Path(__file__).resolve().parent.joinpath(*parts)


def app_icon_png() -> Path:
    return resource_path("app_icon.png")


def app_icon_ico() -> Path:
    return resource_path("app_icon.ico")
