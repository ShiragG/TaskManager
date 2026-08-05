from __future__ import annotations

import logging
import sys
from pathlib import Path

from taskmanager.infrastructure.paths import default_log_path

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

_configured = False


def setup_logging(*, debug: bool = False, log_path: Path | None = None) -> Path:
    """Configure root file logging. ERROR+ always; DEBUG when debug is True."""
    global _configured
    path = Path(log_path) if log_path is not None else default_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    level = logging.DEBUG if debug else logging.ERROR
    root.setLevel(level)

    # Replace existing FileHandlers we own to allow reconfigure after settings save.
    for handler in list(root.handlers):
        if getattr(handler, "_taskmanager_log", False):
            root.removeHandler(handler)
            handler.close()

    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    file_handler._taskmanager_log = True  # type: ignore[attr-defined]
    root.addHandler(file_handler)

    if not _configured:
        _install_excepthook()
        _configured = True

    logging.getLogger(__name__).debug(
        "Logging configured (level=%s, path=%s)",
        logging.getLevelName(level),
        path,
    )
    return path


def _install_excepthook() -> None:
    previous = sys.excepthook

    def _excepthook(exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        if issubclass(exc_type, KeyboardInterrupt):
            previous(exc_type, exc, tb)
            return
        logging.getLogger("taskmanager").exception(
            "Unhandled exception",
            exc_info=(exc_type, exc, tb),
        )
        previous(exc_type, exc, tb)

    sys.excepthook = _excepthook


def install_qt_message_handler() -> None:
    """Route Qt messages to the Python logger when PySide6 is available."""
    try:
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    except ImportError:
        return

    logger = logging.getLogger("qt")

    def _handler(mode, context, message) -> None:  # type: ignore[no-untyped-def]
        text = str(message)
        if mode == QtMsgType.QtFatalMsg:
            logger.error("%s", text)
        elif mode == QtMsgType.QtCriticalMsg:
            logger.error("%s", text)
        elif mode == QtMsgType.QtWarningMsg:
            logger.warning("%s", text)
        elif mode == QtMsgType.QtInfoMsg:
            logger.info("%s", text)
        else:
            logger.debug("%s", text)

    qInstallMessageHandler(_handler)
