from __future__ import annotations

import logging
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
from taskmanager.ui.styles.embedded import STYLESHEETS

logger = logging.getLogger(__name__)


def _style_candidates(filename: str) -> list[Path]:
    candidates: list[Path] = [
        Path(__file__).resolve().parent / "styles" / filename,
    ]
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)
        candidates.append(meipass / "taskmanager" / "ui" / "styles" / filename)
        candidates.append(meipass / filename)
    return candidates


def load_stylesheet(filename: str = "app.qss") -> tuple[str, str]:
    """Load QSS text and a short source label for logging.

    Order: filesystem / PyInstaller datas → importlib.resources → embedded strings.
    """
    for style_path in _style_candidates(filename):
        if style_path.is_file():
            text = style_path.read_text(encoding="utf-8")
            return text, str(style_path)

    try:
        resource = resources.files("taskmanager.ui").joinpath(f"styles/{filename}")
        text = resource.read_text(encoding="utf-8")
        return text, f"importlib.resources:{filename}"
    except Exception:
        logger.debug("importlib.resources miss for %s", filename, exc_info=True)

    embedded = STYLESHEETS.get(filename, "")
    if embedded:
        return embedded, f"embedded:{filename}"
    return "", f"missing:{filename}"


def resolve_theme_mode(theme_mode: str) -> str:
    """Return ``light`` or ``dark`` given settings mode (including system)."""
    if theme_mode == THEME_LIGHT:
        return THEME_LIGHT
    if theme_mode == THEME_DARK:
        return THEME_DARK
    # system — Unknown / Light → light; only explicit Dark → dark
    hints = QGuiApplication.styleHints()
    scheme = hints.colorScheme()
    if scheme == Qt.ColorScheme.Dark:
        return THEME_DARK
    return THEME_LIGHT


def apply_stylesheet(app: QApplication, theme_mode: str = THEME_SYSTEM) -> None:
    app.setStyle("Fusion")

    resolved = resolve_theme_mode(theme_mode)
    if theme_mode == THEME_LIGHT:
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    elif theme_mode == THEME_DARK:
        app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    # system: leave ColorScheme to the OS / Qt defaults

    filename = "app_dark.qss" if resolved == THEME_DARK else "app.qss"
    qss, source = load_stylesheet(filename)
    size = len(qss)
    frozen = bool(getattr(sys, "frozen", False))
    if not qss:
        logger.warning(
            "Stylesheet empty for %s (resolved=%s, source=%s, frozen=%s); UI may look unstyled",
            filename,
            resolved,
            source,
            frozen,
        )
    elif frozen:
        logger.warning(
            "Loaded stylesheet %s (%d bytes) from %s (theme=%s→%s)",
            filename,
            size,
            source,
            theme_mode,
            resolved,
        )
    else:
        logger.debug(
            "Loaded stylesheet %s (%d bytes) from %s (theme=%s→%s)",
            filename,
            size,
            source,
            theme_mode,
            resolved,
        )
    if qss:
        app.setStyleSheet(qss)
    else:
        app.setStyleSheet("")
