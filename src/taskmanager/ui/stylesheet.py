from __future__ import annotations

import sys
from importlib import resources
from pathlib import Path

from PySide6.QtWidgets import QApplication


def load_stylesheet() -> str:
    candidates: list[Path] = [
        Path(__file__).resolve().parent / "styles" / "app.qss",
    ]
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)
        candidates.append(meipass / "taskmanager" / "ui" / "styles" / "app.qss")
        candidates.append(meipass / "app.qss")

    for style_path in candidates:
        if style_path.is_file():
            return style_path.read_text(encoding="utf-8")

    try:
        return resources.files("taskmanager.ui").joinpath("styles/app.qss").read_text(
            encoding="utf-8"
        )
    except Exception:
        return ""


def apply_stylesheet(app: QApplication) -> None:
    qss = load_stylesheet()
    if qss:
        app.setStyleSheet(qss)
