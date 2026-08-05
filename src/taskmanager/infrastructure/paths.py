from __future__ import annotations

import sys
from pathlib import Path


def app_dir() -> Path:
    """Directory that holds the app binary (or CWD when running from source)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def default_settings_path() -> Path:
    return app_dir() / "settings.json"


def default_db_path() -> Path:
    return app_dir() / "taskmanager.db"


def default_log_path() -> Path:
    return app_dir() / "taskmanager.log"


def resolve_work_dir(work_dir: str | Path) -> Path:
    """Resolve work_dir; relative paths are anchored at the app directory."""
    path = Path(work_dir)
    if path.is_absolute():
        return path
    return (app_dir() / path).resolve()
