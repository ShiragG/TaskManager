"""Settings UI for Source modules: enable, GitHub URL, credentials, install zip."""

from __future__ import annotations

import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from taskmanager.services.module_install import fetch_latest_module_release
from taskmanager.services.settings_service import SourceModuleConfig
from taskmanager.services.source_host import SourceHost
from taskmanager.services.source_protocol import SourceModuleError

logger = logging.getLogger(__name__)

HINT_TEXT = (
    "Модули источников — опциональные плагины (zip в папке modules/). "
    "Без модулей локально созданные заявки работают как обычно; "
    "импорт и обновление из источника недоступны."
)


class SourceModulesSettingsWidget(QWidget):
    """Embeddable panel for module enable / install / credentials."""

    def __init__(
        self,
        source_host: SourceHost | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._host = source_host
        self._rows: list[_ModuleRow] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._list_host = QVBoxLayout()
        layout.addLayout(self._list_host)

        add_row = QHBoxLayout()
        add_btn = QPushButton("Добавить модуль…")
        add_btn.setObjectName("secondaryButton")
        add_btn.clicked.connect(self._add_blank)
        add_row.addWidget(add_btn)
        add_row.addStretch()
        layout.addLayout(add_row)

        self.reload_from_host()

    def reload_from_host(self) -> None:
        while self._list_host.count():
            item = self._list_host.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._rows.clear()

        configs: list[SourceModuleConfig] = []
        if self._host is not None:
            seen: set[str] = set()
            for loaded in self._host.list_loaded():
                cfg = loaded.config
                key = cfg.module_id or cfg.github_repo or id(cfg)
                if str(key) in seen:
                    continue
                seen.add(str(key))
                configs.append(cfg)
        for cfg in configs:
            self._add_row(cfg)

    def _add_blank(self) -> None:
        self._add_row(SourceModuleConfig())

    def _add_row(self, cfg: SourceModuleConfig) -> None:
        row = _ModuleRow(cfg, host=self._host, parent=self)
        row.deleted.connect(self._on_row_deleted)
        self._rows.append(row)
        self._list_host.addWidget(row)

    def _on_row_deleted(self, row: "_ModuleRow") -> None:
        if row in self._rows:
            self._rows.remove(row)
        self._list_host.removeWidget(row)
        row.deleteLater()

    def collect_configs(self) -> list[SourceModuleConfig]:
        return [row.to_config() for row in self._rows]

    def persist_credentials(self) -> None:
        if self._host is None:
            return
        for row in self._rows:
            row.save_credentials_if_needed(self._host)


class _ModuleRow(QGroupBox):
    deleted = Signal(object)

    def __init__(
        self,
        cfg: SourceModuleConfig,
        *,
        host: SourceHost | None,
        parent=None,
    ) -> None:
        title = cfg.display_name or cfg.module_id or "Модуль источника"
        super().__init__(title, parent)
        self._host = host
        self._module_id = cfg.module_id
        self._display_name = cfg.display_name
        self._update_asset_name = cfg.update_asset_name
        self._update_asset_pattern = cfg.update_asset_pattern
        self._password_dirty = False

        form = QFormLayout(self)

        self.enabled_cb = QCheckBox("Включён")
        self.enabled_cb.setChecked(cfg.enabled)
        form.addRow(self.enabled_cb)

        self.github_edit = QLineEdit(cfg.github_repo)
        self.github_edit.setPlaceholderText("https://github.com/owner/repo")
        form.addRow("GitHub репозиторий", self.github_edit)

        self.id_label = QLabel(cfg.module_id or "—")
        form.addRow("ID", self.id_label)

        self.version_label = QLabel(cfg.installed_version or "не установлен")
        form.addRow("Версия", self.version_label)

        self.login_edit = QLineEdit(cfg.login)
        form.addRow("Логин", self.login_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("••••••••")
        self.password_edit.textChanged.connect(self._on_password_changed)
        form.addRow("Пароль", self.password_edit)

        auth_row = QHBoxLayout()
        self.auth_check_btn = QPushButton("Проверить вход")
        self.auth_check_btn.setObjectName("secondaryButton")
        self.auth_check_btn.clicked.connect(self._check_login)
        self.auth_status = QLabel("")
        self.auth_status.setStyleSheet("color: #64748b;")
        auth_row.addWidget(self.auth_check_btn)
        auth_row.addWidget(self.auth_status, stretch=1)
        form.addRow(auth_row)

        btn_row = QHBoxLayout()
        check_btn = QPushButton("Проверить релиз…")
        check_btn.setObjectName("secondaryButton")
        check_btn.clicked.connect(self._check_release)
        install_btn = QPushButton("Скачать / обновить zip")
        install_btn.clicked.connect(self._install)
        delete_btn = QPushButton("Удалить")
        delete_btn.setObjectName("secondaryButton")
        delete_btn.clicked.connect(self._delete)
        btn_row.addWidget(check_btn)
        btn_row.addWidget(install_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()
        form.addRow(btn_row)

        if host is not None and cfg.module_id:
            try:
                creds = host.get_credentials(cfg.module_id)
            except SourceModuleError:
                creds = None
            if creds is not None:
                self.login_edit.setText(creds[0])

    def _on_password_changed(self, _text: str) -> None:
        self._password_dirty = True

    def _resolve_password_for_check(self) -> str | None:
        """Password from the form, or saved credentials if the field is empty."""
        typed = self.password_edit.text()
        if typed:
            return typed
        module_id = (self._module_id or "").strip()
        if not module_id or self._host is None:
            return None
        try:
            existing = self._host.get_credentials(module_id)
        except SourceModuleError:
            return None
        if existing is None:
            return None
        login = self.login_edit.text().strip()
        if existing[0] != login:
            return None
        return existing[1]

    def _check_login(self) -> None:
        if self._host is None:
            QMessageBox.warning(self, "Модуль", "Host модулей недоступен")
            return
        module_id = (self._module_id or "").strip()
        if not module_id:
            QMessageBox.warning(
                self, "Модуль", "Сначала установите модуль (скачайте zip)"
            )
            return
        login = self.login_edit.text().strip()
        password = self._resolve_password_for_check()
        if not login:
            QMessageBox.warning(self, "Модуль", "Укажите логин")
            return
        if not password:
            QMessageBox.warning(self, "Модуль", "Укажите пароль")
            return
        self.auth_status.setText("Проверка…")
        self.auth_status.setStyleSheet("color: #64748b;")
        try:
            self._host.check_login(module_id, login, password)
        except SourceModuleError as exc:
            logger.warning("Auth check failed module=%s: %s", module_id, exc)
            self.auth_status.setText(str(exc))
            self.auth_status.setStyleSheet("color: #b91c1c;")
            QMessageBox.warning(self, "Вход", str(exc))
            return
        self.auth_status.setText("OK")
        self.auth_status.setStyleSheet("color: #15803d;")
        QMessageBox.information(self, "Вход", "OK")

    def to_config(self) -> SourceModuleConfig:
        version_text = self.version_label.text()
        return SourceModuleConfig(
            github_repo=self.github_edit.text().strip(),
            enabled=self.enabled_cb.isChecked(),
            module_id=self._module_id or "",
            display_name=self._display_name
            or (self.title() if self.title() != "Модуль источника" else ""),
            installed_version=version_text if version_text != "не установлен" else "",
            login=self.login_edit.text().strip(),
            update_asset_name=self._update_asset_name,
            update_asset_pattern=self._update_asset_pattern,
        )

    def save_credentials_if_needed(self, host: SourceHost) -> None:
        module_id = self._module_id.strip() if self._module_id else ""
        login = self.login_edit.text().strip()
        if not module_id or not login:
            return
        if not self._password_dirty and not self.password_edit.text():
            existing = None
            try:
                existing = host.get_credentials(module_id)
            except SourceModuleError:
                existing = None
            if existing is None:
                return
            if existing[0] != login:
                host.set_credentials(module_id, login, existing[1])
            return
        password = self.password_edit.text()
        if not password:
            return
        host.set_credentials(module_id, login, password)
        self._password_dirty = False
        self.password_edit.clear()

    def _check_release(self) -> None:
        url = self.github_edit.text().strip()
        logger.debug("UI: check module release url=%s", url)
        try:
            release = fetch_latest_module_release(url)
        except SourceModuleError as exc:
            QMessageBox.warning(self, "Модуль", str(exc))
            return
        logger.debug("UI: module release tag=%s", release.tag)
        QMessageBox.information(
            self,
            "Релиз модуля",
            f"Последний релиз: {release.tag}\n"
            f"Архивов zip: {sum(1 for a in release.assets if a.name.endswith('.zip'))}",
        )

    def _install(self) -> None:
        if self._host is None:
            QMessageBox.warning(self, "Модуль", "Host модулей недоступен")
            return
        url = self.github_edit.text().strip()
        logger.debug("UI: install module zip url=%s", url)
        try:
            manifest = self._host.install_from_github(
                url,
                module_id=self._module_id or None,
                enabled=self.enabled_cb.isChecked(),
            )
        except SourceModuleError as exc:
            logger.warning("Module install failed: %s", exc)
            QMessageBox.warning(self, "Модуль", str(exc))
            return
        logger.debug(
            "UI: module installed id=%s version=%s",
            manifest.id,
            manifest.version,
        )
        self._module_id = manifest.id
        self._display_name = manifest.display_name
        self._update_asset_name = manifest.update.asset_name
        self._update_asset_pattern = manifest.update.asset_pattern
        self.id_label.setText(manifest.id)
        self.version_label.setText(manifest.version)
        self.setTitle(manifest.display_name)
        QMessageBox.information(
            self,
            "Модуль",
            f"Установлен «{manifest.display_name}» {manifest.version}",
        )

    def _delete(self) -> None:
        module_id = (self._module_id or "").strip()
        if self._host is None:
            self.deleted.emit(self)
            return
        if not module_id:
            self.deleted.emit(self)
            return
        linked = self._host.repo.count_tasks_for_source_module(module_id)
        msg = (
            f"Удалить модуль «{module_id}»?\n"
            f"Будут удалены zip, запись реестра и учётные данные."
        )
        if linked:
            msg += (
                f"\n\nУ {linked} заявок будет очищена привязка к источнику "
                "(source_module_id / external_id / source_label)."
            )
        reply = QMessageBox.question(
            self,
            "Удалить модуль",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            cleared = self._host.uninstall_module(module_id)
        except SourceModuleError as exc:
            QMessageBox.warning(self, "Модуль", str(exc))
            return
        if cleared:
            QMessageBox.information(
                self,
                "Модуль",
                f"Модуль удалён. Очищена привязка у {cleared} заявок.",
            )
        self.deleted.emit(self)
