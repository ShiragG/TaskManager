from __future__ import annotations

from importlib import resources
from pathlib import Path

from PySide6.QtWidgets import QApplication


def load_stylesheet() -> str:
    style_path = Path(__file__).resolve().parent / "styles" / "app.qss"
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
