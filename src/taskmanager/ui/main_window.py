from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt, QThread, QTimer
from PySide6.QtGui import QAction, QColor, QKeySequence, QMouseEvent, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QMenu,
    QProgressBar,
    QPushButton,
    QSystemTrayIcon,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from taskmanager.domain import (
    Project,
    contrast_foreground,
    html_to_plain,
    is_deadline_warning,
    natural_sort_key,
    priority_color_hex,
    truncate_plain,
)
from taskmanager.infrastructure.logging_setup import setup_logging
from taskmanager.infrastructure.platform_open import PlatformOpenError, open_target
from taskmanager.services.excel_export import ExcelExportError, export_tasks_to_excel
from taskmanager.services.hotkeys import normalize_hotkeys
from taskmanager.services.settings_service import (
    BASE_COLOR_NAMES,
    Settings,
    SettingsStore,
)
from taskmanager.services.task_service import (
    CreateTaskRequest,
    ServiceError,
    TaskService,
    UpdateTaskRequest,
)
from taskmanager.services.update_service import (
    LatestRelease,
    UpdateService,
    asset_name_for_platform,
    current_executable,
    is_frozen,
    launch_restart_helper,
    staged_update_path,
    write_restart_helper,
)
from taskmanager.ui.dialogs import (
    ExcelExportDialog,
    MissingFoldersDialog,
    ProjectDialog,
    RichTextEditDialog,
    TaskDialog,
)
from taskmanager.ui.event_sound_player import EventSoundPlayer
from taskmanager.ui.reminders_window import (
    ReminderEditDialog,
    ReminderNotifyDialog,
    RemindersWindow,
    format_reminder_series,
)
from taskmanager.ui.settings_dialog import SettingsDialog
from taskmanager.ui.stylesheet import apply_stylesheet
from taskmanager.ui.update_worker import UpdateCheckWorker, UpdateDownloadWorker
from taskmanager.version import get_version

logger = logging.getLogger(__name__)

TASK_ID_ROLE = Qt.ItemDataRole.UserRole
SORT_ROLE = Qt.ItemDataRole.UserRole + 1

COL_PRIORITY = 0
COL_NUMBER = 1
COL_STATUS = 2
COL_DATE = 3
COL_DESCRIPTION = 4
COL_COMMENT = 5

SWATCH_SIZE = 22
DESC_COL_WIDTH = 360
MSG_SELECT_ONE = "Выберите одну заявку"


def _format_bytes(n: int) -> str:
    value = float(n)
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if value < 1024 or unit == "ГБ":
            if unit == "Б":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{n} Б"


def _format_speed(bps: float) -> str:
    return f"{_format_bytes(int(bps))}/с"


class SortableItem(QTableWidgetItem):
    """Compare by SORT_ROLE so dates and numbers sort correctly."""

    def __lt__(self, other: QTableWidgetItem) -> bool:  # type: ignore[override]
        left = self.data(SORT_ROLE)
        right = other.data(SORT_ROLE)
        if left is not None and right is not None:
            return left < right
        return super().__lt__(other)


class ColorSwatchButton(QToolButton):
    """Palette swatch; optional right-click removal for custom colors."""

    def __init__(
        self,
        color: str,
        *,
        tooltip: str,
        removable: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.hex_color = color
        self.removable = removable
        self.setToolTip(tooltip)
        self.setFixedSize(SWATCH_SIZE, SWATCH_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        border = "#94a3b8" if color.lower() in {"#ffffff", "#fff"} else "#334155"
        self.setStyleSheet(
            f"QToolButton {{ background-color: {color}; border: 1px solid {border}; "
            f"border-radius: 3px; }}"
            f"QToolButton:hover {{ border: 2px solid #0f766e; }}"
        )
        self._on_remove = None

    def set_remove_handler(self, handler) -> None:
        self._on_remove = handler

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if (
            event.button() == Qt.MouseButton.RightButton
            and self.removable
            and self._on_remove is not None
        ):
            self._on_remove()
            event.accept()
            return
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    def __init__(
        self,
        service: TaskService,
        settings: Settings,
        settings_store: SettingsStore,
        source_host=None,
    ) -> None:
        super().__init__()
        self.service = service
        self.settings = settings
        self.settings_store = settings_store
        self.source_host = source_host
        self._show_hidden = False
        self._show_archive = False
        self._search_query = ""
        self._update_thread: QThread | None = None
        self._update_worker: UpdateCheckWorker | UpdateDownloadWorker | None = None
        self._download_worker: UpdateDownloadWorker | None = None
        self._update_busy = False
        self._pending_update_path: Path | None = None
        self._reminders_window: RemindersWindow | None = None
        self._notified_occurrences: set[tuple[int, str]] = set()
        self._session_started_at = datetime.now()
        self._reminder_tray: QSystemTrayIcon | None = None
        self._event_sound_player = EventSoundPlayer(self)
        self._update_ui: SettingsDialog | None = None

        self.setWindowTitle("TaskManager")
        self.resize(1100, 640)

        self._build_toolbar()
        self._build_central()
        self._build_shortcuts()
        self._sync_mode_actions()
        self._setup_reminder_notifications()

        self.reload_projects()
        self._check_missing_folders()

    def _build_toolbar(self) -> None:
        tb = QToolBar("Главная")
        tb.setMovable(False)
        tb.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.addToolBar(tb)

        self.act_add_project = QAction("Проект", self)
        self.act_add_project.triggered.connect(self.add_project)
        tb.addAction(self.act_add_project)

        self.act_add_task = QAction("Заявка", self)
        self.act_add_task.triggered.connect(self.add_task)
        tb.addAction(self.act_add_task)

        self.act_import_source = QAction("Импорт…", self)
        self.act_import_source.triggered.connect(self.import_from_source)
        tb.addAction(self.act_import_source)

        self.act_edit = QAction("Изменить", self)
        self.act_edit.triggered.connect(self.edit_selected_task)
        tb.addAction(self.act_edit)

        self.act_archive = QAction("В архив", self)
        self.act_archive.triggered.connect(self.archive_selected_task)
        tb.addAction(self.act_archive)

        self.act_restore = QAction("Вернуть", self)
        self.act_restore.triggered.connect(self.restore_selected_task)
        tb.addAction(self.act_restore)

        self.act_hide = QAction("Скрыть", self)
        self.act_hide.triggered.connect(self.hide_selected_tasks)
        tb.addAction(self.act_hide)

        self.act_unhide = QAction("Показать", self)
        self.act_unhide.triggered.connect(self.unhide_selected_tasks)
        tb.addAction(self.act_unhide)

        self.act_delete = QAction("Удалить", self)
        self.act_delete.triggered.connect(self.delete_selected_task)
        tb.addAction(self.act_delete)

        self.act_open_folder = QAction("Открыть папку", self)
        self.act_open_folder.triggered.connect(self.open_selected_folder)
        tb.addAction(self.act_open_folder)

        tb.addSeparator()

        self.act_reminders = QAction("Календарь", self)
        self.act_reminders.triggered.connect(self.open_reminders)
        tb.addAction(self.act_reminders)

        self.act_export = QAction("Excel…", self)
        self.act_export.triggered.connect(self.export_excel)
        tb.addAction(self.act_export)

        self.act_settings = QAction("Настройки", self)
        self.act_settings.triggered.connect(self.open_settings)
        tb.addAction(self.act_settings)

    def _build_central(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Номер, описание или комментарий…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self.search_edit)

        self.hidden_cb = QCheckBox("Скрытые")
        self.hidden_cb.setChecked(False)
        self.hidden_cb.toggled.connect(self._on_hidden_toggled)
        search_row.addWidget(self.hidden_cb)

        self.archive_cb = QCheckBox("Архив")
        self.archive_cb.setChecked(False)
        self.archive_cb.toggled.connect(self._on_archive_toggled)
        search_row.addWidget(self.archive_cb)
        layout.addLayout(search_row)

        palette_row = QHBoxLayout()
        palette_row.addWidget(QLabel("Цвет:"))
        self.palette_host = QWidget()
        self.palette_layout = QHBoxLayout(self.palette_host)
        self.palette_layout.setContentsMargins(0, 0, 0, 0)
        self.palette_layout.setSpacing(4)
        palette_row.addWidget(self.palette_host)
        palette_row.addStretch()
        layout.addLayout(palette_row)
        self._rebuild_color_palette()

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(False)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        tab_bar = self.tabs.tabBar()
        tab_bar.setMovable(True)
        tab_bar.tabMoved.connect(self._on_tab_moved)
        tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tab_bar.customContextMenuRequested.connect(self._show_tab_context_menu)
        layout.addWidget(self.tabs)

        self._update_panel = QWidget()
        update_row = QHBoxLayout(self._update_panel)
        update_row.setContentsMargins(0, 0, 0, 0)
        self._update_label = QLabel("Загрузка обновления…")
        self._update_progress = QProgressBar()
        self._update_progress.setMinimum(0)
        self._update_progress.setMaximum(100)
        self._update_progress.setValue(0)
        self._update_cancel_btn = QPushButton("Отмена")
        self._update_cancel_btn.setObjectName("secondaryButton")
        self._update_cancel_btn.clicked.connect(self._cancel_update_download)
        self._update_restart_btn = QPushButton("Установить и закрыть")
        self._update_restart_btn.clicked.connect(self._restart_with_update)
        self._update_restart_btn.hide()
        update_row.addWidget(self._update_label, stretch=1)
        update_row.addWidget(self._update_progress, stretch=2)
        update_row.addWidget(self._update_cancel_btn)
        update_row.addWidget(self._update_restart_btn)
        self._update_panel.hide()
        layout.addWidget(self._update_panel)

        self.setCentralWidget(central)
        self.statusBar().showMessage("Готово")

    def _rebuild_color_palette(self) -> None:
        while self.palette_layout.count():
            item = self.palette_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        none_btn = ColorSwatchButton("#e2e8f0", tooltip="Без цвета")
        none_btn.setText("∅")
        none_btn.setStyleSheet(
            "QToolButton { background-color: #e2e8f0; border: 1px dashed #64748b; "
            "border-radius: 3px; color: #64748b; font-size: 11px; }"
            "QToolButton:hover { border: 2px solid #0f766e; }"
        )
        none_btn.clicked.connect(lambda: self._apply_color_to_selection(None))
        self.palette_layout.addWidget(none_btn)

        for name, hex_color in self.settings.colors.items():
            removable = name not in BASE_COLOR_NAMES
            btn = ColorSwatchButton(
                hex_color, tooltip=name, removable=removable
            )
            btn.clicked.connect(
                lambda checked=False, c=hex_color: self._apply_color_to_selection(c)
            )
            if removable:
                btn.set_remove_handler(
                    lambda n=name: self._remove_custom_color(n)
                )
            self.palette_layout.addWidget(btn)

        add_btn = QToolButton()
        add_btn.setText("+")
        add_btn.setToolTip("Добавить цвет")
        add_btn.setFixedSize(SWATCH_SIZE, SWATCH_SIZE)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setObjectName("secondaryButton")
        add_btn.clicked.connect(self._add_custom_color)
        self.palette_layout.addWidget(add_btn)
        self.palette_layout.addStretch()

    def _apply_color_to_selection(self, color: str | None) -> None:
        task_ids = self.selected_task_ids()
        if not task_ids:
            self.statusBar().showMessage("Выберите заявку, чтобы задать цвет")
            return
        errors: list[str] = []
        updated = 0
        for task_id in task_ids:
            try:
                if color is None:
                    self.service.update_task(
                        task_id, UpdateTaskRequest(clear_color=True)
                    )
                else:
                    self.service.update_task(
                        task_id, UpdateTaskRequest(color=color)
                    )
                updated += 1
            except ServiceError as exc:
                number = self._task_number_for_error(task_id)
                errors.append(f"{number}: {exc}")
        self.reload_current_tab()
        if errors:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Не удалось изменить цвет у части заявок:\n"
                + "\n".join(errors[:10]),
            )
        elif updated:
            self.statusBar().showMessage(
                "Цвет обновлён"
                if updated == 1
                else f"Цвет обновлён для заявок: {updated}"
            )

    def _task_number_for_error(self, task_id: int) -> str:
        try:
            return self.service.get_task(task_id).number
        except ServiceError:
            return f"#{task_id}"

    def _require_single_task_id(self) -> int | None:
        ids = self.selected_task_ids()
        if len(ids) != 1:
            QMessageBox.information(self, "Уведомление", MSG_SELECT_ONE)
            return None
        return ids[0]

    def _add_custom_color(self) -> None:
        initial = QColor("#cccccc")
        color = QColorDialog.getColor(initial, self, "Выберите цвет")
        if not color.isValid():
            return
        hex_color = color.name()
        name = hex_color
        suffix = 2
        while name in self.settings.colors:
            name = f"{hex_color} ({suffix})"
            suffix += 1
        self.settings.colors[name] = hex_color
        self.settings_store.save(self.settings)
        self._rebuild_color_palette()
        self._apply_color_to_selection(hex_color)

    def _remove_custom_color(self, name: str) -> None:
        if name in BASE_COLOR_NAMES:
            return
        self.settings.colors.pop(name, None)
        self.settings_store.save(self.settings)
        self._rebuild_color_palette()

    def _build_shortcuts(self) -> None:
        for sc in getattr(self, "_shortcuts", []):
            sc.setParent(None)
            sc.deleteLater()
        self._shortcuts: list[QShortcut] = []
        hotkeys = normalize_hotkeys(self.settings.hotkeys)
        mapping = {
            "focus_search": self.focus_search,
            "add_task": self.add_task,
            "reload_current_tab": self.reload_current_tab,
        }
        for action_id, slot in mapping.items():
            seq = QKeySequence(hotkeys[action_id])
            self._shortcuts.append(QShortcut(seq, self, activated=slot))

    def focus_search(self) -> None:
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def _sync_mode_actions(self) -> None:
        archive = self._show_archive
        hidden = self._show_hidden
        self.act_add_task.setEnabled(not archive)
        self.act_import_source.setEnabled(not archive)
        self.act_archive.setVisible(not archive)
        self.act_restore.setVisible(archive)
        self.act_hide.setVisible(not archive and not hidden)
        self.act_unhide.setVisible(not archive and hidden)
        self.act_edit.setEnabled(not archive)
        self.act_delete.setEnabled(not archive)
        self.act_delete.setVisible(not archive)

    # --- data loading ---

    def reload_projects(self) -> None:
        current_id = self.current_project_id()
        self.tabs.blockSignals(True)
        self.tabs.tabBar().blockSignals(True)
        self.tabs.clear()
        for project in self.service.list_projects():
            table = self._make_table()
            self.tabs.addTab(table, project.name)
            self.tabs.tabBar().setTabData(self.tabs.count() - 1, project.id)
        self.tabs.tabBar().blockSignals(False)
        self.tabs.blockSignals(False)

        if current_id is not None:
            for i in range(self.tabs.count()):
                if self.tabs.tabBar().tabData(i) == current_id:
                    self.tabs.setCurrentIndex(i)
                    break
        elif self.tabs.count():
            self.tabs.setCurrentIndex(0)
        self.reload_current_tab()

    # Alias used by older tests
    def reload_directories(self) -> None:
        self.reload_projects()

    def reload_current_tab(self) -> None:
        idx = self.tabs.currentIndex()
        if idx < 0:
            return
        project_id = self.tabs.tabBar().tabData(idx)
        project = next(
            (p for p in self.service.list_projects() if p.id == project_id),
            None,
        )
        if project is None:
            self.reload_projects()
            return
        table = self.tabs.widget(idx)
        assert isinstance(table, QTableWidget)
        self._fill_table(table, project)

    def _make_table(self) -> QTableWidget:
        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(
            ["Приоритет", "Номер", "Статус", "Срок", "Описание", "Комментарий"]
        )
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(False)
        table.setSortingEnabled(True)
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COL_PRIORITY, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_NUMBER, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_DATE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_DESCRIPTION, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_COMMENT, QHeaderView.ResizeMode.Stretch)
        header.resizeSection(COL_DESCRIPTION, DESC_COL_WIDTH)
        header.setMinimumSectionSize(60)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(COL_NUMBER, Qt.SortOrder.AscendingOrder)
        table.verticalHeader().setVisible(False)
        table.doubleClicked.connect(self._on_table_double_clicked)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(
            lambda pos, t=table: self._show_context_menu(t, pos)
        )
        delete_shortcut = QShortcut(QKeySequence.StandardKey.Delete, table)
        delete_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        delete_shortcut.activated.connect(self.delete_selected_task)
        return table

    def _fill_table(self, table: QTableWidget, project: Project) -> None:
        query = self._search_query or None
        tasks = self.service.list_tasks(
            project.id,  # type: ignore[arg-type]
            only_hidden=self._show_hidden,
            archived=self._show_archive,
            query=query,
        )

        table.setSortingEnabled(False)
        table.setRowCount(0)
        today = date.today()
        missed_ids = self.service.task_ids_with_missed_reminders()
        all_cols = (
            COL_PRIORITY,
            COL_NUMBER,
            COL_STATUS,
            COL_DATE,
            COL_DESCRIPTION,
            COL_COMMENT,
        )
        for task in tasks:
            row = table.rowCount()
            table.insertRow(row)

            priority_item = SortableItem(str(task.priority))
            priority_item.setData(TASK_ID_ROLE, task.id)
            priority_item.setData(SORT_ROLE, task.priority)
            priority_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, COL_PRIORITY, priority_item)

            number_text = task.number
            if task.id in missed_ids:
                number_text = f"● {task.number}"
            number_item = SortableItem(number_text)
            number_item.setData(TASK_ID_ROLE, task.id)
            number_item.setData(SORT_ROLE, natural_sort_key(task.number))
            if task.id in missed_ids:
                number_item.setToolTip("Есть пропущенное событие")
            table.setItem(row, COL_NUMBER, number_item)

            status_text = task.display_status
            status_item = SortableItem(status_text)
            status_item.setData(SORT_ROLE, status_text.casefold())
            table.setItem(row, COL_STATUS, status_item)

            date_text = task.date_end.strftime("%d.%m.%Y") if task.date_end else ""
            date_item = SortableItem(date_text)
            date_item.setData(
                SORT_ROLE,
                task.date_end.toordinal() if task.date_end else 0,
            )
            table.setItem(row, COL_DATE, date_item)

            desc_plain = task.description_plain
            desc_item = SortableItem(truncate_plain(desc_plain))
            desc_item.setData(TASK_ID_ROLE, task.id)
            desc_item.setData(SORT_ROLE, desc_plain.casefold())
            table.setItem(row, COL_DESCRIPTION, desc_item)

            comment_plain = task.comment_plain
            comment_item = SortableItem(truncate_plain(comment_plain))
            comment_item.setData(TASK_ID_ROLE, task.id)
            comment_item.setData(SORT_ROLE, comment_plain.casefold())
            table.setItem(row, COL_COMMENT, comment_item)

            if task.color:
                row_bg = QColor(task.color)
                fg = QColor(contrast_foreground(task.color))
                for col in all_cols:
                    item = table.item(row, col)
                    if item:
                        item.setBackground(row_bg)
                        item.setForeground(fg)

            if self.settings.show_priority_colors:
                priority_item.setBackground(QColor(priority_color_hex(task.priority)))
                priority_item.setForeground(
                    QColor(contrast_foreground(priority_color_hex(task.priority)))
                )

            if self.settings.highlight_warnings and is_deadline_warning(
                task.date_end,
                today=today,
                lead_days=self.settings.warning_lead_days,
            ):
                warn = QColor(self.settings.warning_color)
                for col in all_cols:
                    item = table.item(row, col)
                    if item:
                        item.setForeground(warn)

        table.setSortingEnabled(True)
        header = table.horizontalHeader()
        if header.sectionSize(COL_DESCRIPTION) < DESC_COL_WIDTH // 2:
            header.resizeSection(COL_DESCRIPTION, DESC_COL_WIDTH)
        table.sortItems(header.sortIndicatorSection(), header.sortIndicatorOrder())
        if self._show_archive:
            mode = "в архиве"
        elif self._show_hidden:
            mode = "скрытых"
        else:
            mode = "заявок"
        self.statusBar().showMessage(f"{project.name}: {len(tasks)} {mode}")

    def _save_task_html(
        self,
        task_id: int,
        *,
        description: str | None = None,
        comment: str | None = None,
    ) -> None:
        try:
            self.service.update_task(
                task_id,
                UpdateTaskRequest(description=description, comment=comment),
            )
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.reload_current_tab()

    def _on_table_double_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        if index.column() in (COL_DESCRIPTION, COL_COMMENT):
            self._edit_selected_rich_field(index.column())
        else:
            self.edit_selected_task()

    def _edit_selected_rich_field(self, column: int) -> None:
        if self._show_archive:
            QMessageBox.information(
                self, "Уведомление", "Архивные заявки нельзя редактировать — сначала верните"
            )
            return
        task_id = self._require_single_task_id()
        if task_id is None:
            return
        try:
            task = self.service.get_task(task_id)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        if column == COL_DESCRIPTION:
            title = "Описание"
            html = task.description
        else:
            title = "Комментарий"
            html = task.comment
        dialog = RichTextEditDialog(self, title=title, html=html)
        if dialog.exec() != RichTextEditDialog.DialogCode.Accepted:
            return
        if column == COL_DESCRIPTION:
            self._save_task_html(task_id, description=dialog.html)
        else:
            self._save_task_html(task_id, comment=dialog.html)

    # --- selection helpers ---

    def current_project_id(self) -> int | None:
        idx = self.tabs.currentIndex()
        if idx < 0:
            return None
        data = self.tabs.tabBar().tabData(idx)
        return int(data) if data is not None else None

    def current_directory_id(self) -> int | None:
        return self.current_project_id()

    def current_table(self) -> QTableWidget | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, QTableWidget) else None

    def selected_task_id(self) -> int | None:
        ids = self.selected_task_ids()
        return ids[0] if ids else None

    def selected_task_ids(self) -> list[int]:
        table = self.current_table()
        if table is None:
            return []
        model = table.selectionModel()
        if model is None:
            return []
        ids: list[int] = []
        seen: set[int] = set()
        for index in model.selectedRows(COL_NUMBER):
            item = table.item(index.row(), COL_NUMBER)
            if item is None:
                continue
            value = item.data(TASK_ID_ROLE)
            if value is None:
                continue
            task_id = int(value)
            if task_id in seen:
                continue
            seen.add(task_id)
            ids.append(task_id)
        return ids

    # --- actions ---

    def add_project(self) -> None:
        dialog = ProjectDialog(self, title="Новый проект")
        if dialog.exec() != ProjectDialog.DialogCode.Accepted:
            return
        try:
            self.service.create_project(dialog.project_name)
        except ServiceError as exc:
            logger.debug("Create project failed: %s", exc)
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        logger.debug("UI: project created %r", dialog.project_name)
        self.reload_projects()

    def add_directory(self) -> None:
        self.add_project()

    def rename_current_project(self) -> None:
        project_id = self.current_project_id()
        if project_id is None:
            return
        project = next(
            (p for p in self.service.list_projects() if p.id == project_id),
            None,
        )
        if project is None:
            return
        dialog = ProjectDialog(
            self,
            name=project.name,
            title="Изменить проект",
        )
        if dialog.exec() != ProjectDialog.DialogCode.Accepted:
            return
        try:
            self.service.rename_project(project_id, dialog.project_name)
        except ServiceError as exc:
            logger.debug("Rename project failed: %s", exc)
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        logger.debug(
            "UI: project renamed id=%s -> %r", project_id, dialog.project_name
        )
        self.reload_projects()

    def open_current_project_folder(self) -> None:
        project_id = self.current_project_id()
        if project_id is None:
            return
        try:
            path = self.service.project_folder_path(project_id)
            open_target(str(path))
        except (ServiceError, PlatformOpenError) as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))

    def delete_current_project(self) -> None:
        project_id = self.current_project_id()
        if project_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Удаление",
            "Удалить проект? Активные заявки должны быть заархивированы заранее.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_project(project_id, remove_folder=True)
        except ServiceError as exc:
            logger.debug("Delete project failed: %s", exc)
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        logger.debug("UI: project deleted id=%s", project_id)
        self.reload_projects()

    def add_task(self) -> None:
        if self._show_archive:
            QMessageBox.information(
                self, "Уведомление", "В режиме архива нельзя создавать заявки"
            )
            return
        project_id = self.current_project_id()
        if project_id is None:
            QMessageBox.information(self, "Уведомление", "Сначала создайте проект")
            return
        proposed: str | None = None
        initial_number = ""
        if self.settings.autonumber_on_create:
            proposed = self.service.propose_next_number(project_id)
            initial_number = proposed
        dialog = TaskDialog(
            self.settings,
            self,
            title="Новая заявка",
            folder_validator=self._make_create_folder_validator(project_id),
            initial_number=initial_number,
        )
        if dialog.exec() != TaskDialog.DialogCode.Accepted:
            return
        try:
            self.service.create_task(
                CreateTaskRequest(
                    project_id=project_id,
                    number=dialog.number,
                    proposed_number=proposed,
                    description=dialog.description,
                    comment=dialog.comment,
                    date_end=dialog.date_end,
                    color=None,
                    priority=dialog.priority,
                    hidden=dialog.hidden,
                    by_template=dialog.by_template,
                    create_notes_file=dialog.create_notes_file,
                    create_folder=dialog.create_folder,
                    links=dialog.links,
                    workflow_status=dialog.workflow_status,
                )
            )
        except ServiceError as exc:
            logger.debug("Create task failed: %s", exc)
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        logger.debug(
            "UI: task created number=%r project=%s priority=%s",
            dialog.number,
            project_id,
            dialog.priority,
        )
        self.reload_current_tab()

    def import_from_source(self) -> None:
        if self.source_host is None:
            QMessageBox.information(
                self, "Импорт", "Модули источников недоступны"
            )
            return
        if self._show_archive:
            QMessageBox.information(
                self, "Уведомление", "В режиме архива нельзя создавать заявки"
            )
            return
        project_id = self.current_project_id()
        if project_id is None:
            QMessageBox.information(self, "Уведомление", "Сначала создайте проект")
            return
        if not self.source_host.enabled_modules():
            QMessageBox.information(
                self,
                "Импорт",
                "Нет включённых модулей. Установите и включите модуль в Настройках.",
            )
            return

        from taskmanager.ui.source_import_dialog import (
            SourceImportDialog,
            draft_to_dialog_kwargs,
        )

        logger.debug("UI: open import dialog project_id=%s", project_id)
        picker = SourceImportDialog(
            self.source_host, self, project_id=project_id
        )
        picker.bulk_import_requested.connect(
            lambda mid, ids, dlg=picker, pid=project_id: self._bulk_import_from_source(
                dlg, pid, mid, ids
            )
        )
        if picker.exec() != SourceImportDialog.DialogCode.Accepted:
            logger.debug("UI: import dialog cancelled")
            return
        draft = picker.draft
        module_id = picker.module_id
        if draft is None or not module_id:
            return

        kwargs = draft_to_dialog_kwargs(draft)
        dialog = TaskDialog(
            self.settings,
            self,
            folder_validator=self._make_create_folder_validator(project_id),
            source_linked=True,
            initial_source_status=(
                draft.source_status_label or draft.source_status_id or ""
            ),
            **kwargs,
        )
        if dialog.exec() != TaskDialog.DialogCode.Accepted:
            logger.debug("UI: import TaskDialog cancelled")
            return
        logger.debug(
            "UI: import create module=%s external_id=%s number=%r",
            module_id,
            draft.external_id,
            dialog.number,
        )
        try:
            task = self.source_host.create_task_from_draft(
                project_id=project_id,
                module_id=module_id,
                draft=draft,
                create_folder=dialog.create_folder,
                create_notes_file=dialog.create_notes_file,
                by_template=dialog.by_template,
                download_files=False,
                comment=dialog.comment,
                date_end=dialog.date_end,
                hidden=dialog.hidden,
                description_html=dialog.description,
                priority=dialog.priority,
                number=dialog.number,
                links=dialog.links,
            )
            if picker.download_files:
                try:
                    self.source_host.download_task_files(
                        task.id,  # type: ignore[arg-type]
                        create_folder_if_missing=True,
                    )
                except Exception as exc:
                    logger.warning("Download after import: %s", exc)
                    QMessageBox.warning(
                        self,
                        "Файлы",
                        f"Заявка создана, но файлы не скачались:\n{exc}",
                    )
        except Exception as exc:
            from taskmanager.services.source_protocol import SourceModuleError

            if not isinstance(exc, (ServiceError, SourceModuleError)):
                logger.exception("Import create failed")
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.reload_current_tab()

    def _bulk_import_from_source(
        self,
        picker,
        project_id: int,
        module_id: str,
        external_ids: list[str],
    ) -> None:
        """Create Tasks from snapshots without TaskDialog; keep picker open."""
        from taskmanager.services.source_protocol import SourceModuleError

        if self.source_host is None:
            return
        created = 0
        skipped = 0
        errors: list[str] = []
        download = bool(picker.download_files)
        create_folder = self.settings.create_task_folder
        create_notes = self.settings.create_notes_file
        total = len(external_ids)
        picker.begin_bulk_progress(total)
        self.statusBar().showMessage(f"Импорт: 0 из {total}…")
        try:
            for index, external_id in enumerate(external_ids, start=1):
                picker.update_bulk_progress(index - 1, total, external_id)
                self.statusBar().showMessage(
                    f"Импорт: {index - 1} из {total} — {external_id}"
                )
                try:
                    draft = self.source_host.get_item(module_id, external_id)
                    task = self.source_host.create_task_from_draft(
                        project_id=project_id,
                        module_id=module_id,
                        draft=draft,
                        create_folder=create_folder,
                        create_notes_file=create_notes,
                        by_template=False,
                        download_files=False,
                    )
                    if download:
                        try:
                            self.source_host.download_task_files(
                                task.id,  # type: ignore[arg-type]
                                create_folder_if_missing=True,
                            )
                        except Exception as exc:
                            logger.warning(
                                "Download after bulk import %s: %s", external_id, exc
                            )
                            errors.append(f"{external_id}: файлы — {exc}")
                    created += 1
                except ServiceError as exc:
                    msg = str(exc)
                    if "уже импортирован" in msg.lower():
                        skipped += 1
                    else:
                        errors.append(f"{external_id}: {exc}")
                except SourceModuleError as exc:
                    errors.append(f"{external_id}: {exc}")
                except Exception as exc:
                    logger.exception("Bulk import failed for %s", external_id)
                    errors.append(f"{external_id}: {exc}")
                picker.update_bulk_progress(index, total, external_id)
                self.statusBar().showMessage(f"Импорт: {index} из {total}")
        finally:
            picker.end_bulk_progress()

        lines = [f"Создано: {created}"]
        if skipped:
            lines.append(f"Пропущено (уже импортированы): {skipped}")
        if errors:
            lines.append(f"Ошибки: {len(errors)}")
            lines.extend(errors[:10])
            if len(errors) > 10:
                lines.append(f"…и ещё {len(errors) - 10}")
        QMessageBox.information(self, "Импорт", "\n".join(lines))
        picker.refresh_imported_marks()
        self.reload_current_tab()
        self.statusBar().showMessage(
            f"Импорт завершён: создано {created}"
            + (f", пропущено {skipped}" if skipped else "")
            + (f", ошибок {len(errors)}" if errors else "")
        )

    def refresh_selected_from_source(self) -> None:
        if self.source_host is None:
            return
        task_id = self._require_single_task_id()
        if task_id is None:
            return
        try:
            task = self.service.get_task(task_id)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        if not task.has_source:
            QMessageBox.information(
                self, "Источник", "У заявки нет привязки к источнику"
            )
            return
        answer = QMessageBox.question(
            self,
            "Обновить из источника",
            "Перезаписать описание, приоритет и служебные ссылки из источника?\n"
            "Комментарий не изменится.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        logger.debug("UI: refresh from source task_id=%s", task_id)
        try:
            self.source_host.refresh_task_from_source(task_id)
        except Exception as exc:
            logger.warning("Refresh from source failed: %s", exc)
            QMessageBox.warning(self, "Источник", str(exc))
            return
        logger.debug("UI: refresh from source done task_id=%s", task_id)
        self.reload_current_tab()

    def download_selected_source_files(self) -> None:
        if self.source_host is None:
            return
        task_id = self._require_single_task_id()
        if task_id is None:
            return
        logger.debug("UI: download source files task_id=%s", task_id)
        try:
            saved = self.source_host.download_task_files(
                task_id, create_folder_if_missing=True
            )
        except Exception as exc:
            logger.warning("Download source files failed: %s", exc)
            QMessageBox.warning(self, "Файлы", str(exc))
            return
        logger.debug("UI: download source files done count=%s", len(saved))
        if saved:
            QMessageBox.information(
                self,
                "Файлы",
                "Скачано:\n" + "\n".join(saved),
            )
        else:
            QMessageBox.information(
                self, "Файлы", "Новых файлов нет (уже скачаны или список пуст)."
            )
        self.reload_current_tab()

    def _make_create_folder_validator(self, project_id: int):
        def validate(dialog: TaskDialog) -> str | None:
            need_folder = (
                dialog.create_folder or dialog.by_template or dialog.create_notes_file
            )
            try:
                self.service.validate_create_folder(
                    project_id,
                    dialog.number,
                    create_folder=need_folder,
                    by_template=dialog.by_template,
                )
            except ServiceError as exc:
                return str(exc)
            return None

        return validate

    def edit_selected_task(self) -> None:
        if self._show_archive:
            QMessageBox.information(
                self, "Уведомление", "Архивные заявки нельзя редактировать — сначала верните"
            )
            return
        task_id = self._require_single_task_id()
        if task_id is None:
            return
        try:
            task = self.service.get_task(task_id)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return

        def validate(dialog: TaskDialog) -> str | None:
            try:
                self.service.validate_update_folder(task_id, dialog.number)
            except ServiceError as exc:
                return str(exc)
            return None

        reminder_rows = [
            (series.id, format_reminder_series(series))
            for series in self.service.list_reminders(task_id)
            if series.id is not None
        ]

        def on_delete_reminder(reminder_id: int) -> bool:
            try:
                self.service.delete_reminder(reminder_id)
            except ServiceError as exc:
                QMessageBox.warning(self, "Ошибка", str(exc))
                return False
            if self._reminders_window is not None:
                self._reminders_window.reload()
            return True

        def on_reminders_changed() -> None:
            if self._reminders_window is not None:
                self._reminders_window.reload()

        dialog = TaskDialog(
            self.settings,
            self,
            task=task,
            title="Изменить заявку",
            allow_template=False,
            folder_validator=validate,
            reminder_rows=reminder_rows,
            on_delete_reminder=on_delete_reminder,
            reminder_service=self.service,
            on_reminders_changed=on_reminders_changed,
        )
        if dialog.exec() != TaskDialog.DialogCode.Accepted:
            return
        try:
            self.service.update_task(
                task_id,
                UpdateTaskRequest(
                    number=dialog.number,
                    description=dialog.description,
                    comment=dialog.comment,
                    date_end=dialog.date_end,
                    clear_date_end=dialog.date_end is None,
                    priority=dialog.priority,
                    hidden=dialog.hidden,
                    links=dialog.links,
                    workflow_status=(
                        None if task.has_source else dialog.workflow_status
                    ),
                ),
            )
        except ServiceError as exc:
            logger.debug("Update task failed: %s", exc)
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        logger.debug("UI: task updated id=%s number=%r", task_id, dialog.number)
        self.reload_current_tab()

    def archive_selected_task(self) -> None:
        task_ids = self.selected_task_ids()
        if not task_ids:
            QMessageBox.information(self, "Уведомление", "Выберите заявку")
            return
        if len(task_ids) == 1:
            prompt = (
                "Перед переносом закройте файлы заявки (если есть папка). Продолжить?"
            )
        else:
            prompt = (
                f"Перед переносом закройте файлы {len(task_ids)} заявок "
                "(если есть папки). Продолжить?"
            )
        answer = QMessageBox.question(self, "Архив", prompt)
        if answer != QMessageBox.StandardButton.Yes:
            return
        errors: list[str] = []
        archived = 0
        for task_id in task_ids:
            try:
                self.service.archive_task(task_id)
                archived += 1
            except ServiceError as exc:
                logger.debug("Archive task failed id=%s: %s", task_id, exc)
                errors.append(f"{self._task_number_for_error(task_id)}: {exc}")
        logger.debug(
            "UI: tasks archived count=%s errors=%s", archived, len(errors)
        )
        self.reload_current_tab()
        if errors:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Не удалось заархивировать часть заявок:\n" + "\n".join(errors[:10]),
            )
        elif archived:
            self.statusBar().showMessage(
                "Заявка в архиве"
                if archived == 1
                else f"В архиве заявок: {archived}"
            )

    def restore_selected_task(self) -> None:
        task_ids = self.selected_task_ids()
        if not task_ids:
            QMessageBox.information(self, "Уведомление", "Выберите заявку")
            return
        errors: list[str] = []
        restored = 0
        for task_id in task_ids:
            try:
                self.service.restore_task(task_id)
                restored += 1
            except ServiceError as exc:
                logger.debug("Restore task failed id=%s: %s", task_id, exc)
                errors.append(f"{self._task_number_for_error(task_id)}: {exc}")
        logger.debug(
            "UI: tasks restored count=%s errors=%s", restored, len(errors)
        )
        self.reload_current_tab()
        if errors:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Не удалось вернуть часть заявок:\n" + "\n".join(errors[:10]),
            )
        elif restored:
            self.statusBar().showMessage(
                "Заявка возвращена"
                if restored == 1
                else f"Возвращено заявок: {restored}"
            )

    def hide_selected_tasks(self) -> None:
        self._set_hidden_on_selection(True)

    def unhide_selected_tasks(self) -> None:
        self._set_hidden_on_selection(False)

    def _set_hidden_on_selection(self, hidden: bool) -> None:
        if self._show_archive:
            return
        task_ids = self.selected_task_ids()
        if not task_ids:
            QMessageBox.information(self, "Уведомление", "Выберите заявку")
            return
        errors: list[str] = []
        changed = 0
        for task_id in task_ids:
            try:
                self.service.update_task(
                    task_id, UpdateTaskRequest(hidden=hidden)
                )
                changed += 1
            except ServiceError as exc:
                errors.append(f"{self._task_number_for_error(task_id)}: {exc}")
        self.reload_current_tab()
        if errors:
            title = "Скрыть" if hidden else "Показать"
            QMessageBox.warning(
                self,
                title,
                "Не удалось изменить часть заявок:\n" + "\n".join(errors[:10]),
            )
        elif changed:
            if hidden:
                msg = (
                    "Заявка скрыта"
                    if changed == 1
                    else f"Скрыто заявок: {changed}"
                )
            else:
                msg = (
                    "Заявка показана"
                    if changed == 1
                    else f"Показано заявок: {changed}"
                )
            self.statusBar().showMessage(msg)

    def delete_selected_task(self) -> None:
        if self._show_archive:
            QMessageBox.information(
                self,
                "Уведомление",
                "В режиме архива удаление недоступно — сначала верните заявку",
            )
            return
        task_ids = self.selected_task_ids()
        if not task_ids:
            QMessageBox.information(self, "Уведомление", "Выберите заявку")
            return
        if len(task_ids) == 1:
            prompt = "Удалить заявку и её папку (если есть)? Действие необратимо."
        else:
            prompt = (
                f"Удалить {len(task_ids)} заявок и их папки (если есть)? "
                "Действие необратимо."
            )
        answer = QMessageBox.question(self, "Удаление", prompt)
        if answer != QMessageBox.StandardButton.Yes:
            return
        errors: list[str] = []
        deleted = 0
        for task_id in task_ids:
            try:
                self.service.delete_task(task_id)
                deleted += 1
            except ServiceError as exc:
                logger.debug("Delete task failed id=%s: %s", task_id, exc)
                errors.append(f"{self._task_number_for_error(task_id)}: {exc}")
        logger.debug("UI: tasks deleted count=%s errors=%s", deleted, len(errors))
        self.reload_current_tab()
        if errors:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Не удалось удалить часть заявок:\n" + "\n".join(errors[:10]),
            )
        elif deleted:
            self.statusBar().showMessage(
                "Заявка удалена" if deleted == 1 else f"Удалено заявок: {deleted}"
            )

    def open_selected_folder(self) -> None:
        task_id = self._require_single_task_id()
        if task_id is None:
            return
        try:
            path = self.service.open_task_folder(task_id)
            open_target(str(path))
        except (ServiceError, PlatformOpenError) as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
        else:
            self.reload_current_tab()

    def copy_selected_task_number(self) -> None:
        task_id = self._require_single_task_id()
        if task_id is None:
            return
        try:
            task = self.service.get_task(task_id)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        QApplication.clipboard().setText(task.number)
        self.statusBar().showMessage("Номер скопирован")

    def export_excel(self) -> None:
        projects = self.service.list_projects()
        if not projects:
            QMessageBox.information(self, "Уведомление", "Нет проектов для экспорта")
            return
        archive_months_by_project: dict[int, list[str]] = {}
        for project in projects:
            if project.id is None:
                continue
            archive_months_by_project[int(project.id)] = (
                self.service.repo.list_archive_months(int(project.id))
            )
        dialog = ExcelExportDialog(
            projects,
            self,
            archive_months_by_project=archive_months_by_project,
        )
        if dialog.exec() != ExcelExportDialog.DialogCode.Accepted:
            return
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить Excel",
            str(Path.home() / "tasks.xlsx"),
            "Excel (*.xlsx)",
        )
        if not dest:
            return
        if not dest.lower().endswith(".xlsx"):
            dest += ".xlsx"
        try:
            path = export_tasks_to_excel(
                self.service,
                Path(dest),
                project_ids=dialog.selected_project_ids,
                include_hidden=dialog.include_hidden,
                include_archived=dialog.include_archived,
                archive_months_by_project=dialog.selected_archive_months,
            )
        except ExcelExportError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.statusBar().showMessage(f"Экспорт сохранён: {path}")
        QMessageBox.information(self, "Excel", f"Файл сохранён:\n{path}")

    def open_settings(self) -> None:
        dialog = SettingsDialog(
            self.settings,
            self.settings_store,
            self,
            on_check_updates=self.start_update_check,
            source_host=self.source_host,
        )
        self._update_ui = dialog
        dialog.cancel_update_requested.connect(self._cancel_update_download)
        dialog.install_update_requested.connect(self._restart_with_update)
        dialog.finished.connect(self._on_settings_finished)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return
        self.settings = dialog.settings
        self.service.settings = self.settings
        self.service.fs.settings = self.settings
        if self.source_host is not None:
            self.source_host.settings = self.settings
            self.source_host.reload()
        setup_logging(debug=self.settings.debug_logging)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_stylesheet(app, self.settings.theme_mode)
        logger.debug(
            "Settings saved (debug_logging=%s theme=%s)",
            self.settings.debug_logging,
            self.settings.theme_mode,
        )
        self._rebuild_color_palette()
        self._build_shortcuts()
        self.reload_projects()

    def _on_settings_finished(self, _result: int = 0) -> None:
        self._update_ui = None
        if self._update_busy or self._pending_update_path is not None:
            self._update_panel.show()

    def _update_parent(self) -> QWidget:
        host = self._update_ui
        if host is not None and host.isVisible():
            return host
        return self

    def _update_host(self) -> QWidget:
        host = self._update_ui
        if host is not None and host.isVisible():
            return host
        return self

    def start_update_check(self) -> None:
        if self._update_busy:
            QMessageBox.information(
                self._update_parent(),
                "Обновления",
                "Обновление уже выполняется…",
            )
            self.statusBar().showMessage("Обновление уже выполняется…")
            return
        logger.debug("Starting update check")
        self._update_busy = True
        host = self._update_host()
        host._update_panel.show()
        host._update_label.setText("Проверка обновлений…")
        host._update_progress.hide()
        host._update_cancel_btn.hide()
        host._update_restart_btn.hide()
        self.statusBar().showMessage("Проверка обновлений…")
        thread = QThread(self)
        worker = UpdateCheckWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._on_update_check_succeeded)
        worker.failed.connect(self._on_update_check_failed)
        worker.succeeded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_update_thread_finished)
        self._update_thread = thread
        self._update_worker = worker
        thread.start()

    def _on_update_check_succeeded(self, release: object) -> None:
        assert isinstance(release, LatestRelease)
        current = get_version()
        updater = UpdateService()
        logger.info(
            "Update check: current=%s remote=%s (tag=%s)",
            current,
            release.version,
            release.tag,
        )
        if not updater.is_newer(release.tag, current):
            msg = (
                f"Установлена актуальная версия ({current}; remote {release.version})"
            )
            self.statusBar().showMessage(msg)
            logger.info(
                "Already up to date: current=%s remote=%s",
                current,
                release.version,
            )
            self._update_busy = False
            self._hide_update_panel()
            QMessageBox.information(self._update_parent(), "Обновления", msg)
            return

        asset_name = asset_name_for_platform()
        asset = updater.find_asset(release, asset_name)
        if asset is None:
            msg = f"В релизе {release.tag} нет файла «{asset_name}»."
            logger.error(msg)
            self.statusBar().showMessage(msg)
            self._update_busy = False
            self._hide_update_panel()
            QMessageBox.warning(self._update_parent(), "Обновления", msg)
            return

        answer = QMessageBox.question(
            self._update_parent(),
            "Обновления",
            f"Доступна версия {release.version} (сейчас {current}).\n"
            f"Скачать «{asset.name}»?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.statusBar().showMessage("Загрузка обновления не начата")
            self._update_busy = False
            self._hide_update_panel()
            return

        dest = staged_update_path()
        self._start_update_download(asset, dest)

    def _on_update_check_failed(self, message: str) -> None:
        logger.error("Update check failed: %s", message)
        self.statusBar().showMessage(f"Ошибка обновления: {message}")
        self._update_busy = False
        self._hide_update_panel()
        QMessageBox.warning(
            self._update_parent(),
            "Обновления",
            f"Ошибка обновления: {message}",
        )

    def _start_update_download(self, asset, dest: Path) -> None:
        self._pending_update_path = None
        host = self._update_host()
        host._update_panel.show()
        host._update_restart_btn.hide()
        host._update_cancel_btn.show()
        host._update_progress.show()
        host._update_label.setText(f"Загрузка «{asset.name}»…")
        host._update_progress.setRange(0, 0)
        host._update_progress.setValue(0)
        host._update_cancel_btn.setEnabled(True)
        self.statusBar().showMessage("Загрузка обновления…")

        thread = QThread(self)
        worker = UpdateDownloadWorker(asset, dest)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_update_progress)
        worker.succeeded.connect(self._on_update_download_succeeded)
        worker.failed.connect(self._on_update_download_failed)
        worker.cancelled.connect(self._on_update_download_cancelled)
        worker.succeeded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_update_thread_finished)
        self._update_thread = thread
        self._update_worker = worker
        self._download_worker = worker
        thread.start()

    def _on_update_progress(
        self, bytes_done: int, total: object, speed: float
    ) -> None:
        host = self._update_host()
        total_int = int(total) if isinstance(total, int) and total > 0 else None
        if total_int:
            host._update_progress.setRange(0, 100)
            host._update_progress.setValue(
                min(100, int(bytes_done * 100 / total_int))
            )
            pct = bytes_done * 100 / total_int
            host._update_label.setText(
                f"Загрузка… {pct:.0f}% · {_format_speed(speed)}"
            )
        else:
            host._update_progress.setRange(0, 0)
            host._update_label.setText(
                f"Загрузка… {_format_bytes(bytes_done)} · {_format_speed(speed)}"
            )

    def _on_update_download_succeeded(self, path: object) -> None:
        assert isinstance(path, Path)
        self._download_worker = None
        self._update_busy = False
        self._pending_update_path = path
        host = self._update_host()
        host._update_progress.hide()
        host._update_cancel_btn.hide()
        host._update_panel.show()
        if is_frozen():
            banner = (
                "Обновление готово. «Установить и закрыть» — после закрытия "
                "файл заменят; затем запустите приложение снова вручную."
            )
            host._update_label.setText(banner)
            self.statusBar().showMessage(f"Обновление готово: {path}")
            host._update_restart_btn.show()
        else:
            msg = "Загрузка обновления завершена"
            host._update_label.setText(msg)
            self.statusBar().showMessage(f"{msg}: {path}")
            host._update_restart_btn.hide()
            QMessageBox.information(
                self._update_parent(),
                "Обновления",
                f"Файл сохранён:\n{path}\n\n"
                "В режиме разработки замените исполняемый файл вручную "
                "и перезапустите приложение.",
            )
        logger.info("Update download finished: %s", path)

    def _restart_with_update(self) -> None:
        if self._pending_update_path is None or not self._pending_update_path.is_file():
            QMessageBox.warning(
                self._update_parent(), "Обновления", "Файл обновления не найден"
            )
            return
        if not is_frozen():
            QMessageBox.information(
                self._update_parent(),
                "Обновления",
                "Автозамена доступна только в собранном приложении.",
            )
            return
        target = current_executable()
        try:
            helper = write_restart_helper(
                new_path=self._pending_update_path,
                target_path=target,
                pid=os.getpid(),
            )
            launch_restart_helper(helper)
        except OSError as exc:
            QMessageBox.warning(
                self._update_parent(),
                "Обновления",
                f"Не удалось запустить helper:\n{exc}",
            )
            return
        logger.info("Install-and-close via helper %s (no relaunch)", helper)
        QApplication.instance().quit()

    def _on_update_download_failed(self, message: str) -> None:
        self._hide_update_panel()
        self._download_worker = None
        self._update_busy = False
        logger.error("Update download failed: %s", message)
        self.statusBar().showMessage(f"Ошибка загрузки: {message}")
        QMessageBox.warning(
            self._update_parent(), "Обновления", f"Ошибка загрузки: {message}"
        )

    def _on_update_download_cancelled(self) -> None:
        self._hide_update_panel()
        self._download_worker = None
        self._update_busy = False
        self.statusBar().showMessage("Загрузка отменена")

    def _cancel_update_download(self) -> None:
        if self._download_worker is not None:
            host = self._update_host()
            host._update_cancel_btn.setEnabled(False)
            host._update_label.setText("Отмена…")
            self._download_worker.request_cancel()

    def _hide_update_panel(self) -> None:
        for host in {self, self._update_ui} - {None}:
            host._update_panel.hide()
            host._update_progress.show()
            host._update_cancel_btn.show()
            host._update_restart_btn.hide()
            host._update_progress.setRange(0, 100)
            host._update_progress.setValue(0)
        self._pending_update_path = None

    def _on_update_thread_finished(self) -> None:
        sender = self.sender()
        if sender is self._update_thread:
            self._update_thread = None
            self._update_worker = None

    def _on_search_changed(self, text: str) -> None:
        self._search_query = text.strip()
        self.reload_current_tab()

    def _on_hidden_toggled(self, checked: bool) -> None:
        self._show_hidden = checked
        if checked and self._show_archive:
            self.archive_cb.blockSignals(True)
            self.archive_cb.setChecked(False)
            self.archive_cb.blockSignals(False)
            self._show_archive = False
        self._sync_mode_actions()
        self.reload_current_tab()

    def _on_archive_toggled(self, checked: bool) -> None:
        self._show_archive = checked
        if checked and self._show_hidden:
            self.hidden_cb.blockSignals(True)
            self.hidden_cb.setChecked(False)
            self.hidden_cb.blockSignals(False)
            self._show_hidden = False
        self._sync_mode_actions()
        self.reload_current_tab()

    def _on_tab_changed(self, _index: int) -> None:
        self.reload_current_tab()

    def _on_tab_moved(self, _from: int, _to: int) -> None:
        ids: list[int] = []
        for i in range(self.tabs.count()):
            pid = self.tabs.tabBar().tabData(i)
            if pid is not None:
                ids.append(int(pid))
        try:
            self.service.reorder_projects(ids)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            self.reload_projects()

    def _show_tab_context_menu(self, pos) -> None:
        tab_bar = self.tabs.tabBar()
        index = tab_bar.tabAt(pos)
        if index < 0:
            return
        self.tabs.setCurrentIndex(index)
        menu = QMenu(self)
        menu.addAction("Изменить", self.rename_current_project)
        menu.addAction("Открыть папку", self.open_current_project_folder)
        menu.addAction("Удалить", self.delete_current_project)
        menu.exec(tab_bar.mapToGlobal(pos))

    def _ensure_context_row_selected(self, table: QTableWidget, index) -> None:
        """Select the clicked row only if it is not already in the selection."""
        if not index.isValid():
            return
        model = table.selectionModel()
        selected_rows = (
            {i.row() for i in model.selectedRows()} if model is not None else set()
        )
        if index.row() not in selected_rows:
            table.selectRow(index.row())

    def _show_context_menu(self, table: QTableWidget, pos) -> None:
        index = table.indexAt(pos)
        self._ensure_context_row_selected(table, index)
        task_ids = self.selected_task_ids()
        task_id = task_ids[0] if len(task_ids) == 1 else None
        menu = QMenu(self)
        if not self._show_archive:
            menu.addAction("Изменить", self.edit_selected_task)
        menu.addAction("Копировать номер", self.copy_selected_task_number)
        menu.addAction("Открыть папку", self.open_selected_folder)
        if self._show_archive:
            menu.addAction("Вернуть", self.restore_selected_task)
        else:
            menu.addAction("В архив", self.archive_selected_task)
            if self._show_hidden:
                menu.addAction("Показать", self.unhide_selected_tasks)
            else:
                menu.addAction("Скрыть", self.hide_selected_tasks)
            menu.addAction("Удалить", self.delete_selected_task)
            if task_id is not None:
                menu.addAction("Событие…", self.add_reminder_for_selected)

        if task_id is not None:
            try:
                task = self.service.get_task(task_id)
            except ServiceError:
                task = None
            if task and task.has_source and not self._show_archive:
                menu.addSeparator()
                menu.addAction(
                    "Обновить из источника…", self.refresh_selected_from_source
                )
                menu.addAction(
                    "Скачать файлы источника…", self.download_selected_source_files
                )
            if task and task.links:
                links_menu = menu.addMenu("Открыть ссылку")
                for link in task.links:
                    links_menu.addAction(
                        link.name,
                        lambda checked=False, t=link.target: self._open_link(t),
                    )

        menu.exec(table.viewport().mapToGlobal(pos))

    def _open_link(self, target: str) -> None:
        try:
            open_target(target)
        except PlatformOpenError as exc:
            QMessageBox.warning(self, "Предупреждение", str(exc))

    def open_reminders(self) -> None:
        if self._reminders_window is None:
            self._reminders_window = RemindersWindow(self.service, self)
            self._reminders_window.open_task_requested.connect(self.reveal_task)
        self._reminders_window.reload()
        self._reminders_window.show()
        self._reminders_window.raise_()
        self._reminders_window.activateWindow()

    def add_reminder_for_selected(self) -> None:
        task_id = self._require_single_task_id()
        if task_id is None:
            return
        try:
            task = self.service.get_task(task_id)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        dialog = ReminderEditDialog(self.service, self, task=task)
        if dialog.exec() != ReminderEditDialog.DialogCode.Accepted:
            return
        try:
            dialog.save_to_service()
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.reload_current_tab()
        if self._reminders_window is not None:
            self._reminders_window.reload()

    def reveal_task(self, task_id: int) -> None:
        try:
            task = self.service.get_task(task_id)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        if task.is_archived:
            if not self._show_archive:
                self.archive_cb.setChecked(True)
        elif task.hidden:
            if not self._show_hidden:
                self.hidden_cb.setChecked(True)
        else:
            if self._show_archive:
                self.archive_cb.setChecked(False)
            if self._show_hidden:
                self.hidden_cb.setChecked(False)
        for i in range(self.tabs.count()):
            if self.tabs.tabBar().tabData(i) == task.project_id:
                self.tabs.setCurrentIndex(i)
                break
        self.reload_current_tab()
        table = self.current_table()
        if table is None:
            return
        for row in range(table.rowCount()):
            item = table.item(row, COL_NUMBER)
            if item is not None and int(item.data(TASK_ID_ROLE) or 0) == task_id:
                table.selectRow(row)
                break
        if not task.is_archived:
            self.edit_selected_task()

    def _setup_reminder_notifications(self) -> None:
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._reminder_tray = QSystemTrayIcon(self.windowIcon(), self)
            self._reminder_tray.setToolTip("TaskManager")
            self._reminder_tray.messageClicked.connect(self._on_tray_reminder_clicked)
            self._reminder_tray.show()
        self._reminder_timer = QTimer(self)
        self._reminder_timer.setInterval(15_000)
        self._reminder_timer.timeout.connect(self._poll_due_reminders)
        self._reminder_timer.start()
        self._pending_notify: tuple[int, datetime, int | None] | None = None
        self._snoozed_until: dict[tuple[int, str], datetime] = {}

    def _poll_due_reminders(self) -> None:
        now = datetime.now()
        for series, occ, task, project in self.service.list_missed_reminders(now=now):
            if occ <= self._session_started_at:
                continue
            if series.id is None:
                continue
            key = (series.id, occ.isoformat(timespec="seconds"))
            snooze_until = self._snoozed_until.get(key)
            if snooze_until is not None:
                if now < snooze_until:
                    continue
                self._snoozed_until.pop(key, None)
                self._notified_occurrences.discard(key)
            if key in self._notified_occurrences:
                continue
            self._notified_occurrences.add(key)
            self._notify_reminder(series, occ, task, project)

    def _notify_reminder(self, series, occ: datetime, task=None, project=None) -> None:
        repeating = " · повторяемое" if series.is_repeating else ""
        plain = html_to_plain(series.text) or "—"
        if task is not None and project is not None:
            title = f"{project.name} / №{task.number}"
        else:
            title = plain
        heading = f"{occ.strftime('%d.%m.%Y %H:%M')}{repeating}"
        body_html = f"<p>{heading}</p>{series.text or '—'}"
        task_id = task.id if task is not None else None
        if series.id is not None:
            self._pending_notify = (series.id, occ, task_id)
        if (
            self.settings.event_os_notification
            and self._reminder_tray is not None
        ):
            self._reminder_tray.showMessage(
                title,
                f"{heading}  {plain}",
                QSystemTrayIcon.MessageIcon.Information,
                8000,
            )
        if self.settings.event_sound_enabled:
            self._event_sound_player.play(self.settings.event_sound_path)
        popup = ReminderNotifyDialog(
            title,
            body_html,
            self,
            snooze_default_minutes=self.settings.event_snooze_minutes,
        )
        if series.id is not None:
            popup.accepted.connect(
                lambda sid=series.id, o=occ: self._acknowledge_occurrence(sid, o)
            )
            popup.snooze_requested.connect(
                lambda minutes, sid=series.id, o=occ: self._snooze_event(
                    sid, o, minutes
                )
            )
            if task_id is not None:
                popup.open_task_requested.connect(
                    lambda tid=task_id: self.reveal_task(tid)
                )
            else:
                popup.open_task_btn.hide()
        popup.show()
        self.reload_current_tab()
        if self._reminders_window is not None:
            self._reminders_window.reload()

    def _snooze_event(
        self, series_id: int, occ: datetime, minutes: int
    ) -> None:
        key = (series_id, occ.isoformat(timespec="seconds"))
        self._snoozed_until[key] = datetime.now() + timedelta(minutes=int(minutes))
        self._notified_occurrences.add(key)

    def _acknowledge_occurrence(self, series_id: int, occ: datetime) -> None:
        key = (series_id, occ.isoformat(timespec="seconds"))
        self._snoozed_until.pop(key, None)
        try:
            self.service.acknowledge_reminder(series_id, occ)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
        self.reload_current_tab()
        if self._reminders_window is not None:
            self._reminders_window.reload()

    def _acknowledge_and_reveal(
        self, series_id: int, occ: datetime, task_id: int
    ) -> None:
        self._acknowledge_occurrence(series_id, occ)
        self.reveal_task(task_id)

    def _on_tray_reminder_clicked(self) -> None:
        pending = self._pending_notify
        if pending is None:
            return
        series_id, occ, task_id = pending
        if task_id is None:
            self._acknowledge_occurrence(series_id, occ)
            return
        self._acknowledge_and_reveal(series_id, occ, task_id)

    def _check_missing_folders(self) -> None:
        missing = self.service.check_missing_folders()
        if not missing:
            return
        dialog = MissingFoldersDialog(missing, self)
        if dialog.exec() != MissingFoldersDialog.DialogCode.Accepted:
            return
        for task_id in dialog.recreate_ids:
            try:
                self.service.recreate_task_folder(task_id)
            except ServiceError as exc:
                QMessageBox.warning(self, "Ошибка", str(exc))
        for task_id in dialog.clear_ids:
            try:
                self.service.clear_task_folder_flag(task_id)
            except ServiceError as exc:
                QMessageBox.warning(self, "Ошибка", str(exc))
        self.reload_current_tab()
