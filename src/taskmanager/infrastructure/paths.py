from __future__ import annotations

import os
from pathlib import Path


def app_data_dir(app_name: str = "taskmanager") -> Path:
    """Return the per-user application data directory (creates it if needed)."""
    system = os.name
    if system == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        # XDG on Linux; also fine on macOS for this app
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / app_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_db_path() -> Path:
    return app_data_dir() / "taskmanager.db"
