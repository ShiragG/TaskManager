from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from taskmanager.infrastructure.logging_setup import (
    install_qt_message_handler,
    setup_logging,
)
from taskmanager.infrastructure.paths import (
    default_db_path,
    default_settings_path,
    resolve_work_dir,
)
from taskmanager.infrastructure.single_instance import InstanceGuard
from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.resources import app_icon_png
from taskmanager.services.settings_service import SettingsStore
from taskmanager.services.source_host import SourceHost
from taskmanager.services.task_service import TaskService
from taskmanager.ui.main_window import MainWindow
from taskmanager.ui.stylesheet import apply_stylesheet

logger = logging.getLogger(__name__)


def _application(argv: list[str]) -> QApplication:
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication(argv)


def run(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv
    app = _application(argv)
    app.setQuitOnLastWindowClosed(True)

    icon_path = app_icon_png()
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    guard = InstanceGuard()
    if not guard.try_become_primary():
        guard.notify_existing()
        return 0

    settings_store = SettingsStore(default_settings_path())
    settings = settings_store.load()
    setup_logging(debug=settings.debug_logging)
    install_qt_message_handler()
    apply_stylesheet(app, settings.theme_mode)
    logger.debug("TaskManager starting")

    work_dir = resolve_work_dir(settings.work_dir)
    if not work_dir.is_dir():
        logger.error("Work directory missing: %s", work_dir)
        QMessageBox.critical(
            None,
            "Ошибка",
            f"Рабочая директория не найдена:\n{work_dir}\n"
            "Исправьте settings.json или создайте папку.",
        )
        guard.release()
        return 1

    repo = SqliteRepository(default_db_path())
    service = TaskService(repo, settings)
    source_host = SourceHost(
        repo,
        settings,
        service,
        pending_migration=settings_store.pending_source_module_migration,
    )
    # Clear one-shot migration payload after apply
    settings_store.pending_source_module_migration = []
    window = MainWindow(service, settings, settings_store, source_host=source_host)
    window.setWindowIcon(app.windowIcon())
    guard.show_requested.connect(window.bring_to_front)
    window.show()
    QTimer.singleShot(0, window.run_startup_update_checks)
    try:
        code = app.exec()
    finally:
        guard.release()
        repo.close()
    return code


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
