"""Separate scrollable dialog for Source module settings."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
)

from taskmanager.services.settings_service import Settings, SettingsStore
from taskmanager.services.source_host import SourceHost
from taskmanager.ui.source_modules_settings import (
    HINT_TEXT,
    SourceModulesSettingsWidget,
)


class SourceModulesSettingsDialog(QDialog):
    """Modules enable / install / credentials — not embedded in main Settings."""

    def __init__(
        self,
        settings: Settings,
        store: SettingsStore,
        source_host: SourceHost | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Модули источников")
        self.setMinimumSize(560, 420)
        self.resize(620, 520)
        self._settings = settings
        self._store = store
        self._source_host = source_host

        layout = QVBoxLayout(self)

        hint = QLabel(HINT_TEXT)
        hint.setObjectName("sourceModulesHint")
        hint.setWordWrap(True)
        hint.setMinimumHeight(48)
        hint.setStyleSheet("color: #64748b;")
        layout.addWidget(hint)

        self.check_module_updates_cb = QCheckBox(
            "Проверять наличие обновлений модулей при запуске"
        )
        self.check_module_updates_cb.setChecked(
            settings.check_module_updates_on_startup
        )
        layout.addWidget(self.check_module_updates_cb)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._modules_widget = SourceModulesSettingsWidget(source_host, scroll)
        scroll.setWidget(self._modules_widget)
        layout.addWidget(scroll)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        try:
            self._modules_widget.persist_credentials()
        except Exception as exc:
            QMessageBox.warning(
                self, "Модули", f"Не удалось сохранить учётные данные:\n{exc}"
            )
            return
        if self._source_host is not None:
            self._source_host.replace_registry(self._modules_widget.collect_configs())
            self._source_host.reload()
            self._source_host.refresh_catalogs()
        self._settings.check_module_updates_on_startup = (
            self.check_module_updates_cb.isChecked()
        )
        self._store.save(self._settings)
        self.accept()
