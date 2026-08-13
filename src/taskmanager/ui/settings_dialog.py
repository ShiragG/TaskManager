from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from taskmanager.infrastructure.event_sounds import (
    CUSTOM_SOUND_SENTINEL,
    first_preferred_sound_path,
    list_system_sound_files,
    sound_choice_label,
)
from taskmanager.infrastructure.paths import resolve_work_dir
from taskmanager.services.hotkeys import (
    DEFAULT_HOTKEYS,
    HOTKEY_LABELS,
    HOTKEY_ORDER,
    hotkeys_to_store,
    normalize_hotkeys,
    validate_hotkeys,
)
from taskmanager.services.settings_service import (
    SNOOZE_LABELS,
    SNOOZE_MINUTES,
    THEME_DARK,
    THEME_LIGHT,
    THEME_SYSTEM,
    Settings,
    SettingsStore,
    parse_snooze_minutes,
)
from taskmanager.ui.about_dialog import AboutDialog
from taskmanager.ui.event_sound_player import EventSoundPlayer
from taskmanager.ui.source_modules_dialog import SourceModulesSettingsDialog
from taskmanager.version import get_version


class SettingsDialog(QDialog):
    cancel_update_requested = Signal()
    install_update_requested = Signal()

    def __init__(
        self,
        settings: Settings,
        store: SettingsStore,
        parent=None,
        *,
        on_check_updates=None,
        source_host=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(620)
        self.setMinimumHeight(520)
        self._store = store
        self._settings = settings
        self._on_check_updates = on_check_updates
        self._source_host = source_host

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs, stretch=1)

        general = QWidget()
        tasks = QWidget()
        events = QWidget()
        hotkeys_page = QWidget()
        tabs.addTab(general, "Общие")
        tabs.addTab(tasks, "Заявки")
        tabs.addTab(events, "События")
        tabs.addTab(hotkeys_page, "Горячие клавиши")

        self._build_general(general, settings)
        self._build_tasks(tasks, settings)
        self._build_events(events, settings)
        self._build_hotkeys(hotkeys_page, settings)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_general(self, page: QWidget, settings: Settings) -> None:
        layout = QVBoxLayout(page)
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

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Светлая", THEME_LIGHT)
        self.theme_combo.addItem("Тёмная", THEME_DARK)
        self.theme_combo.addItem("Как в системе", THEME_SYSTEM)
        idx = self.theme_combo.findData(settings.theme_mode)
        self.theme_combo.setCurrentIndex(idx if idx >= 0 else 2)
        form.addRow("Тема", self.theme_combo)

        self.debug_logging_cb = QCheckBox("Подробный лог (DEBUG/INFO)")
        self.debug_logging_cb.setChecked(settings.debug_logging)
        form.addRow(self.debug_logging_cb)

        layout.addLayout(form)

        modules_row = QHBoxLayout()
        modules_btn = QPushButton("Модули источников…")
        modules_btn.setObjectName("secondaryButton")
        modules_btn.clicked.connect(self._open_modules)
        modules_row.addWidget(modules_btn)
        modules_row.addStretch()
        layout.addLayout(modules_row)

        hint = QLabel(
            "Метаданные заявок хранятся в SQLite рядом с исполняемым файлом. "
            "Папка заявки опциональна; при наличии имя совпадает с номером."
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

        self._update_panel = QWidget()
        update_row = QHBoxLayout(self._update_panel)
        update_row.setContentsMargins(0, 0, 0, 0)
        self._update_label = QLabel("Загрузка обновления…")
        self._update_label.setWordWrap(True)
        self._update_progress = QProgressBar()
        self._update_progress.setMinimum(0)
        self._update_progress.setMaximum(100)
        self._update_progress.setValue(0)
        self._update_cancel_btn = QPushButton("Отмена")
        self._update_cancel_btn.setObjectName("secondaryButton")
        self._update_cancel_btn.clicked.connect(self.cancel_update_requested.emit)
        self._update_restart_btn = QPushButton("Установить и закрыть")
        self._update_restart_btn.clicked.connect(self.install_update_requested.emit)
        self._update_restart_btn.hide()
        update_row.addWidget(self._update_label, stretch=1)
        update_row.addWidget(self._update_progress, stretch=2)
        update_row.addWidget(self._update_cancel_btn)
        update_row.addWidget(self._update_restart_btn)
        self._update_panel.hide()
        layout.addWidget(self._update_panel)

        layout.addStretch()

    def _build_tasks(self, page: QWidget, settings: Settings) -> None:
        layout = QVBoxLayout(page)
        form = QFormLayout()

        self.create_folder_cb = QCheckBox("Создавать папку заявки по умолчанию")
        self.create_folder_cb.setChecked(settings.create_task_folder)
        form.addRow(self.create_folder_cb)

        self.create_notes_cb = QCheckBox("Создавать файл заметок по умолчанию")
        self.create_notes_cb.setChecked(settings.create_notes_file)
        form.addRow(self.create_notes_cb)

        self.autonumber_cb = QCheckBox("Автонумерация при создании")
        self.autonumber_cb.setChecked(settings.autonumber_on_create)
        form.addRow(self.autonumber_cb)

        self.show_priority_colors_cb = QCheckBox("Цвета приоритета в таблице")
        self.show_priority_colors_cb.setChecked(settings.show_priority_colors)
        form.addRow(self.show_priority_colors_cb)

        self.highlight_cb = QCheckBox("Подсвечивать сроки (включая ближайшие)")
        self.highlight_cb.setChecked(settings.highlight_warnings)
        form.addRow(self.highlight_cb)

        self.lead_days_spin = QSpinBox()
        self.lead_days_spin.setRange(0, 365)
        self.lead_days_spin.setValue(settings.warning_lead_days)
        self.lead_days_spin.setSuffix(" дн.")
        self.lead_days_spin.setMinimumWidth(120)
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
        layout.addStretch()

    def _build_events(self, page: QWidget, settings: Settings) -> None:
        layout = QVBoxLayout(page)
        form = QFormLayout()

        self.event_sound_cb = QCheckBox("Звук при событии")
        self.event_sound_cb.setChecked(settings.event_sound_enabled)
        form.addRow(self.event_sound_cb)

        self.event_sound_combo = QComboBox()
        self.preview_sound_btn = QPushButton("Прослушать")
        self.preview_sound_btn.setObjectName("secondaryButton")
        self.preview_sound_btn.clicked.connect(self._preview_event_sound)
        sound_row = QHBoxLayout()
        sound_row.addWidget(self.event_sound_combo, stretch=1)
        sound_row.addWidget(self.preview_sound_btn)
        form.addRow("Файл звука", sound_row)
        self._sound_player = EventSoundPlayer(self)
        self._fill_sound_combo(settings.event_sound_path)
        self.event_sound_combo.currentIndexChanged.connect(self._on_sound_combo_changed)

        self.event_os_notification_cb = QCheckBox("Системное уведомление ОС")
        self.event_os_notification_cb.setChecked(settings.event_os_notification)
        form.addRow(self.event_os_notification_cb)

        self.snooze_combo = QComboBox()
        for minutes in SNOOZE_MINUTES:
            self.snooze_combo.addItem(SNOOZE_LABELS[minutes], minutes)
        snooze_idx = self.snooze_combo.findData(
            parse_snooze_minutes(settings.event_snooze_minutes)
        )
        self.snooze_combo.setCurrentIndex(snooze_idx if snooze_idx >= 0 else 3)
        form.addRow("«Напомнить через» по умолчанию", self.snooze_combo)

        layout.addLayout(form)
        layout.addStretch()

    def _build_hotkeys(self, page: QWidget, settings: Settings) -> None:
        layout = QVBoxLayout(page)
        self.hotkeys_table = QTableWidget(len(HOTKEY_ORDER), 3)
        self.hotkeys_table.setHorizontalHeaderLabels(["Действие", "Сочетание", ""])
        self.hotkeys_table.verticalHeader().setVisible(False)
        self.hotkeys_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.hotkeys_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.hotkeys_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.hotkeys_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        current_hotkeys = normalize_hotkeys(settings.hotkeys)
        self._hotkey_edits: dict[str, QKeySequenceEdit] = {}
        for row, action_id in enumerate(HOTKEY_ORDER):
            name_item = QTableWidgetItem(HOTKEY_LABELS[action_id])
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.hotkeys_table.setItem(row, 0, name_item)
            edit = QKeySequenceEdit(QKeySequence(current_hotkeys[action_id]))
            self._hotkey_edits[action_id] = edit
            self.hotkeys_table.setCellWidget(row, 1, edit)
            reset_btn = QPushButton("Сброс")
            reset_btn.setObjectName("secondaryButton")
            reset_btn.clicked.connect(
                lambda _checked=False, aid=action_id: self._reset_hotkey(aid)
            )
            self.hotkeys_table.setCellWidget(row, 2, reset_btn)
        layout.addWidget(self.hotkeys_table)

    def _open_modules(self) -> None:
        dialog = SourceModulesSettingsDialog(
            self._settings, self._store, self._source_host, self
        )
        dialog.exec()

    def _reset_hotkey(self, action_id: str) -> None:
        edit = self._hotkey_edits.get(action_id)
        if edit is None:
            return
        edit.setKeySequence(QKeySequence(DEFAULT_HOTKEYS[action_id]))

    def _collect_hotkeys(self) -> dict[str, str]:
        raw: dict[str, str] = {}
        for action_id, edit in self._hotkey_edits.items():
            raw[action_id] = edit.keySequence().toString(
                QKeySequence.SequenceFormat.PortableText
            )
        return raw

    def _open_about(self) -> None:
        AboutDialog(self).exec()

    def _fill_sound_combo(self, selected_path: str) -> None:
        self.event_sound_combo.blockSignals(True)
        self.event_sound_combo.clear()
        paths = [str(path) for path in list_system_sound_files()]
        if selected_path and selected_path not in paths:
            paths.insert(0, selected_path)
        for path in paths:
            self.event_sound_combo.addItem(sound_choice_label(path), path)
        self.event_sound_combo.addItem("Свой файл…", CUSTOM_SOUND_SENTINEL)
        if selected_path:
            idx = self.event_sound_combo.findData(selected_path)
            self.event_sound_combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            preferred = first_preferred_sound_path()
            idx = self.event_sound_combo.findData(preferred) if preferred else -1
            if idx >= 0:
                self.event_sound_combo.setCurrentIndex(idx)
            elif self.event_sound_combo.count() > 1:
                self.event_sound_combo.setCurrentIndex(0)
        self._sound_combo_index = self.event_sound_combo.currentIndex()
        self.event_sound_combo.blockSignals(False)

    def _on_sound_combo_changed(self, index: int) -> None:
        if self.event_sound_combo.itemData(index) != CUSTOM_SOUND_SENTINEL:
            self._sound_combo_index = index
            return
        chosen, _filter = QFileDialog.getOpenFileName(
            self,
            "Звук события",
            "",
            "Звук (*.wav *.ogg *.oga *.flac);;Все файлы (*)",
        )
        if chosen:
            self._ensure_sound_combo_path(chosen)
            self._sound_combo_index = self.event_sound_combo.currentIndex()
            return
        self.event_sound_combo.blockSignals(True)
        self.event_sound_combo.setCurrentIndex(self._sound_combo_index)
        self.event_sound_combo.blockSignals(False)

    def _ensure_sound_combo_path(self, path: str) -> None:
        idx = self.event_sound_combo.findData(path)
        if idx < 0:
            insert_at = max(0, self.event_sound_combo.count() - 1)
            self.event_sound_combo.insertItem(
                insert_at, sound_choice_label(path), path
            )
            idx = insert_at
        self.event_sound_combo.setCurrentIndex(idx)

    def _preview_event_sound(self) -> None:
        path = self.event_sound_combo.currentData()
        if not path or path == CUSTOM_SOUND_SENTINEL:
            return
        self._sound_player.play(str(path))

    def _current_event_sound_path(self) -> str:
        path = self.event_sound_combo.currentData()
        if not path or path == CUSTOM_SOUND_SENTINEL:
            return self._settings.event_sound_path
        return str(path)

    def _browse_work_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Рабочая директория", self.work_dir_edit.text()
        )
        if path:
            self.work_dir_edit.setText(path)

    def _sync_warning_swatch(self, text: str) -> None:
        color = QColor(text.strip() or "#ff0000")
        if not color.isValid():
            color = QColor("#ff0000")
        self.warning_color_btn.setStyleSheet(
            f"QPushButton {{ background-color: {color.name()}; "
            f"border: 1px solid #334155; border-radius: 3px; }}"
        )

    def _pick_warning_color(self) -> None:
        current = QColor(self.warning_color_edit.text().strip() or "#ff0000")
        if not current.isValid():
            current = QColor("#ff0000")
        chosen = QColorDialog.getColor(current, self, "Цвет предупреждения")
        if chosen.isValid():
            self.warning_color_edit.setText(chosen.name())

    def _check_updates(self) -> None:
        if self._on_check_updates is not None:
            self._on_check_updates()
            return
        QMessageBox.information(
            self,
            "Обновления",
            "Проверка обновлений недоступна в этом контексте.",
        )

    def _save(self) -> None:
        work_dir = self.work_dir_edit.text().strip()
        if not work_dir:
            QMessageBox.warning(self, "Ошибка", "Укажите рабочую директорию")
            return
        path = resolve_work_dir(work_dir)
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

        warning_color = self.warning_color_edit.text().strip() or "#ff0000"
        if not QColor(warning_color).isValid():
            QMessageBox.warning(self, "Ошибка", "Некорректный цвет предупреждения")
            return

        raw_hotkeys = self._collect_hotkeys()
        hotkey_error = validate_hotkeys(raw_hotkeys)
        if hotkey_error:
            QMessageBox.warning(self, "Горячие клавиши", hotkey_error)
            return
        hotkeys = hotkeys_to_store(raw_hotkeys)

        self._settings.work_dir = work_dir
        self._settings.template_name = template
        self._settings.archive_name = archive
        self._settings.theme_mode = self.theme_combo.currentData()
        self._settings.highlight_warnings = self.highlight_cb.isChecked()
        self._settings.warning_lead_days = self.lead_days_spin.value()
        self._settings.warning_color = warning_color
        self._settings.create_task_folder = self.create_folder_cb.isChecked()
        self._settings.create_notes_file = self.create_notes_cb.isChecked()
        self._settings.autonumber_on_create = self.autonumber_cb.isChecked()
        self._settings.show_priority_colors = self.show_priority_colors_cb.isChecked()
        self._settings.debug_logging = self.debug_logging_cb.isChecked()
        self._settings.event_sound_enabled = self.event_sound_cb.isChecked()
        self._settings.event_sound_path = self._current_event_sound_path()
        self._settings.event_os_notification = self.event_os_notification_cb.isChecked()
        self._settings.event_snooze_minutes = parse_snooze_minutes(
            self.snooze_combo.currentData()
        )
        self._settings.hotkeys = hotkeys
        self._store.save(self._settings)
        self.accept()

    @property
    def settings(self) -> Settings:
        return self._settings
