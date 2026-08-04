from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from taskmanager.infrastructure.platform_open import PlatformOpenError, open_target
from taskmanager.services.settings_service import Settings, SettingsStore
from taskmanager.services.update_service import (
    UpdateError,
    UpdateService,
    asset_name_for_platform,
)
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

        self.highlight_cb = QCheckBox("Подсвечивать сроки (включая ближайшие)")
        self.highlight_cb.setChecked(settings.highlight_warnings)
        form.addRow(self.highlight_cb)

        self.lead_days_spin = QSpinBox()
        self.lead_days_spin.setRange(0, 365)
        self.lead_days_spin.setValue(settings.warning_lead_days)
        self.lead_days_spin.setSuffix(" дн.")
        form.addRow("За сколько дней предупреждать", self.lead_days_spin)

        self.warning_color_edit = QLineEdit(settings.warning_color)
        self.warning_color_btn = QPushButton()
        self.warning_color_btn.setFixedSize(28, 28)
        self.warning_color_btn.setToolTip("Выбрать цвет")
        self.warning_color_btn.clicked.connect(self._pick_warning_color)
        self.warning_color_edit.textChanged.connect(self._sync_warning_swatch)
        color_row = QHBoxLayout()
        color_row.addWidget(self.warning_color_btn)
        color_row.addWidget(self.warning_color_edit)
        form.addRow("Цвет предупреждения", color_row)
        self._sync_warning_swatch(self.warning_color_edit.text())

        layout.addLayout(form)
        hint = QLabel(
            "Метаданные заявок хранятся в SQLite (каталог данных приложения). "
            "Имя папки заявки совпадает с номером; при смене номера папка "
            "переименовывается автоматически."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b;")
        layout.addWidget(hint)

        footer = QHBoxLayout()
        version_label = QLabel(f"Версия {get_version()}")
        version_label.setStyleSheet("color: #64748b;")
        footer.addWidget(version_label)
        footer.addStretch()
        update_btn = QPushButton("Проверить обновления…")
        update_btn.setObjectName("secondaryButton")
        update_btn.clicked.connect(self._check_updates)
        footer.addWidget(update_btn)
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

    def _sync_warning_swatch(self, text: str) -> None:
        color = QColor(text.strip() or "#8B0000")
        if not color.isValid():
            color = QColor("#8B0000")
        self.warning_color_btn.setStyleSheet(
            f"QPushButton {{ background-color: {color.name()}; "
            f"border: 1px solid #334155; border-radius: 3px; }}"
        )

    def _pick_warning_color(self) -> None:
        current = QColor(self.warning_color_edit.text().strip() or "#8B0000")
        if not current.isValid():
            current = QColor("#8B0000")
        chosen = QColorDialog.getColor(current, self, "Цвет предупреждения")
        if chosen.isValid():
            self.warning_color_edit.setText(chosen.name())

    def _check_updates(self) -> None:
        updater = UpdateService()
        try:
            release = updater.fetch_latest_release()
        except UpdateError as exc:
            QMessageBox.warning(self, "Обновления", str(exc))
            return

        current = get_version()
        if not updater.is_newer(release.tag, current):
            QMessageBox.information(
                self,
                "Обновления",
                f"Установлена актуальная версия ({current}).",
            )
            return

        asset_name = asset_name_for_platform()
        asset = updater.find_asset(release, asset_name)
        if asset is None:
            QMessageBox.warning(
                self,
                "Обновления",
                f"В релизе {release.tag} нет файла «{asset_name}».",
            )
            return

        answer = QMessageBox.question(
            self,
            "Обновления",
            f"Доступна версия {release.version} (сейчас {current}).\n"
            f"Скачать «{asset.name}»?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        default_name = asset.name
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить обновление",
            str(Path.home() / default_name),
            "Все файлы (*)",
        )
        if not dest:
            return

        try:
            saved = updater.download_asset(asset, Path(dest))
        except UpdateError as exc:
            QMessageBox.warning(self, "Обновления", str(exc))
            return

        QMessageBox.information(
            self,
            "Обновления",
            f"Файл сохранён:\n{saved}\n\n"
            "Закройте приложение и замените исполняемый файл вручную.",
        )
        try:
            open_target(str(saved.parent))
        except PlatformOpenError:
            pass

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

        warning_color = self.warning_color_edit.text().strip() or "#8B0000"
        if not QColor(warning_color).isValid():
            QMessageBox.warning(self, "Ошибка", "Некорректный цвет предупреждения")
            return

        self._settings.work_dir = work_dir
        self._settings.template_name = template
        self._settings.archive_name = archive
        self._settings.highlight_warnings = self.highlight_cb.isChecked()
        self._settings.warning_lead_days = self.lead_days_spin.value()
        self._settings.warning_color = warning_color
        self._store.save(self._settings)
        self.accept()

    @property
    def settings(self) -> Settings:
        return self._settings
