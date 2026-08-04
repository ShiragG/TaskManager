from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from taskmanager.infrastructure.paths import default_db_path, default_settings_path
from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.resources import app_icon_png
from taskmanager.services.settings_service import SettingsStore
from taskmanager.services.task_service import TaskService
from taskmanager.ui.main_window import MainWindow
from taskmanager.ui.stylesheet import apply_stylesheet


def run(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv
    app = QApplication(argv)
    apply_stylesheet(app)

    icon_path = app_icon_png()
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    settings_store = SettingsStore(default_settings_path())
    settings = settings_store.load()

    if not Path(settings.work_dir).is_dir():
        QMessageBox.critical(
            None,
            "Ошибка",
            f"Рабочая директория не найдена:\n{settings.work_dir}\n"
            "Исправьте settings.json или создайте папку.",
        )
        return 1

    repo = SqliteRepository(default_db_path())
    service = TaskService(repo, settings)
    window = MainWindow(service, settings, settings_store)
    window.setWindowIcon(app.windowIcon())
    window.show()
    code = app.exec()
    repo.close()
    return code


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
