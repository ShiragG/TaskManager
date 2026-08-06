from __future__ import annotations

import sys
from importlib import resources
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from taskmanager.services.settings_service import (
    THEME_DARK,
    THEME_LIGHT,
    THEME_SYSTEM,
)


def _style_candidates(filename: str) -> list[Path]:
    candidates: list[Path] = [
        Path(__file__).resolve().parent / "styles" / filename,
    ]
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)
        candidates.append(meipass / "taskmanager" / "ui" / "styles" / filename)
        candidates.append(meipass / filename)
    return candidates


def load_stylesheet(filename: str = "app.qss") -> str:
    for style_path in _style_candidates(filename):
        if style_path.is_file():
            return style_path.read_text(encoding="utf-8")

    try:
        return resources.files("taskmanager.ui").joinpath(f"styles/{filename}").read_text(
            encoding="utf-8"
        )
    except Exception:
        return ""


def resolve_theme_mode(theme_mode: str) -> str:
    """Return ``light`` or ``dark`` given settings mode (including system)."""
    if theme_mode == THEME_LIGHT:
        return THEME_LIGHT
    if theme_mode == THEME_DARK:
        return THEME_DARK
    # system
    hints = QGuiApplication.styleHints()
    scheme = hints.colorScheme()
    if scheme == Qt.ColorScheme.Dark:
        return THEME_DARK
    return THEME_LIGHT


def apply_stylesheet(app: QApplication, theme_mode: str = THEME_SYSTEM) -> None:
    resolved = resolve_theme_mode(theme_mode)
    filename = "app_dark.qss" if resolved == THEME_DARK else "app.qss"
    qss = load_stylesheet(filename)
    if qss:
        app.setStyleSheet(qss)
