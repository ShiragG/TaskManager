from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from taskmanager.services.settings_service import Settings, SettingsStore
from taskmanager.ui.about_dialog import AboutDialog
from taskmanager.version import get_version


class SettingsDialog(QDialog):
    def __init__(
        self,
        settings: Settings,
        store: SettingsStore,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(480)
        self._store = store
        self._settings = settings

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.work_dir_edit = QLineEdit(settings.work_dir)
        browse = QPushButton("…")
        browse.setObjectName("secondaryButton")
        browse.setFixedWidth(36)
        browse.clicked.connect(self._browse_work_dir)
        work_row = QHBoxLayout()
        work_row.addWidget(self.work_dir_edit)
        work_row.addWidget(browse)
        form.addRow("Рабочая директория", work_row)

        self.template_edit = QLineEdit(settings.template_name)
        form.addRow("Имя шаблона", self.template_edit)

        self.archive_edit = QLineEdit(settings.archive_name)
        form.addRow("Имя архива", self.archive_edit)

        self.highlight_cb = QCheckBox("Подсвечивать просроченные заявки")
        self.highlight_cb.setChecked(settings.highlight_warnings)
        form.addRow(self.highlight_cb)

        self.warning_color_edit = QLineEdit(settings.warning_color)
        form.addRow("Цвет предупреждения", self.warning_color_edit)

        layout.addLayout(form)
        hint = QLabel(
            "Метаданные заявок хранятся в SQLite (каталог данных приложения). "
            "Не переименовывайте папки заявок вручную."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b;")
        layout.addWidget(hint)

        footer = QHBoxLayout()
        version_label = QLabel(f"Версия {get_version()}")
        version_label.setStyleSheet("color: #64748b;")
        footer.addWidget(version_label)
        footer.addStretch()
        about_btn = QPushButton("О приложении…")
        about_btn.setObjectName("secondaryButton")
        about_btn.clicked.connect(self._open_about)
        footer.addWidget(about_btn)
        layout.addLayout(footer)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _open_about(self) -> None:
        AboutDialog(self).exec()

    def _browse_work_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Рабочая директория", self.work_dir_edit.text()
        )
        if path:
            self.work_dir_edit.setText(path)

    def _save(self) -> None:
        work_dir = self.work_dir_edit.text().strip()
        if not work_dir:
            QMessageBox.warning(self, "Ошибка", "Укажите рабочую директорию")
            return
        path = Path(work_dir)
        if not path.is_dir():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                QMessageBox.warning(self, "Ошибка", f"Не удалось создать папку:\n{exc}")
                return

        template = self.template_edit.text().strip() or ".template"
        archive = self.archive_edit.text().strip() or ".archive"
        if template == archive:
            QMessageBox.warning(
                self, "Ошибка", "Имя шаблона и архива не должны совпадать"
            )
            return

        self._settings.work_dir = work_dir
        self._settings.template_name = template
        self._settings.archive_name = archive
        self._settings.highlight_warnings = self.highlight_cb.isChecked()
        self._settings.warning_color = self.warning_color_edit.text().strip() or "#8B0000"
        self._store.save(self._settings)
        self.accept()

    @property
    def settings(self) -> Settings:
        return self._settings
