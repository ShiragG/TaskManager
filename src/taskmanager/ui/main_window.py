from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QKeySequence, QMouseEvent, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QMenu,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from taskmanager.domain import Directory, is_deadline_warning
from taskmanager.infrastructure.platform_open import PlatformOpenError, open_target
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
from taskmanager.ui.dialogs import DirectoryDialog, TaskDialog
from taskmanager.ui.settings_dialog import SettingsDialog

TASK_ID_ROLE = Qt.ItemDataRole.UserRole
SORT_ROLE = Qt.ItemDataRole.UserRole + 1

COL_NUMBER = 0
COL_DATE = 1
COL_DESCRIPTION = 2

SWATCH_SIZE = 22


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
    ) -> None:
        super().__init__()
        self.service = service
        self.settings = settings
        self.settings_store = settings_store
        self._show_hidden = False
        self._search_query = ""

        self.setWindowTitle("TaskManager")
        self.resize(1000, 640)

        self._build_toolbar()
        self._build_central()
        self._build_shortcuts()

        self.reload_directories()
        self._check_missing_folders()

    def _build_toolbar(self) -> None:
        tb = QToolBar("Главная")
        tb.setMovable(False)
        tb.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.addToolBar(tb)

        self.act_add_dir = QAction("Директория", self)
        self.act_add_dir.triggered.connect(self.add_directory)
        tb.addAction(self.act_add_dir)

        self.act_add_task = QAction("Заявка", self)
        self.act_add_task.triggered.connect(self.add_task)
        tb.addAction(self.act_add_task)

        self.act_edit = QAction("Изменить", self)
        self.act_edit.triggered.connect(self.edit_selected_task)
        tb.addAction(self.act_edit)

        self.act_archive = QAction("В архив", self)
        self.act_archive.triggered.connect(self.archive_selected_task)
        tb.addAction(self.act_archive)

        self.act_delete = QAction("Удалить", self)
        self.act_delete.triggered.connect(self.delete_selected_task)
        tb.addAction(self.act_delete)

        self.act_open_folder = QAction("Открыть папку", self)
        self.act_open_folder.triggered.connect(self.open_selected_folder)
        tb.addAction(self.act_open_folder)

        tb.addSeparator()

        self.act_settings = QAction("Настройки", self)
        self.act_settings.triggered.connect(self.open_settings)
        tb.addAction(self.act_settings)

    def _build_central(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Номер или описание…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self.search_edit)

        self.hidden_cb = QCheckBox("Скрытые")
        self.hidden_cb.setChecked(False)
        self.hidden_cb.toggled.connect(self._on_hidden_toggled)
        search_row.addWidget(self.hidden_cb)
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
        tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tab_bar.customContextMenuRequested.connect(self._show_tab_context_menu)
        layout.addWidget(self.tabs)

        self.setCentralWidget(central)
        self.statusBar().showMessage("Готово")

    def _rebuild_color_palette(self) -> None:
        while self.palette_layout.count():
            item = self.palette_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        none_btn = ColorSwatchButton("#ffffff", tooltip="Без цвета")
        none_btn.setText("∅")
        none_btn.setStyleSheet(
            "QToolButton { background-color: #ffffff; border: 1px solid #94a3b8; "
            "border-radius: 3px; color: #64748b; font-size: 11px; }"
            "QToolButton:hover { border: 2px solid #0f766e; }"
        )
        none_btn.clicked.connect(lambda: self._apply_color_to_selection("#ffffff"))
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

    def _apply_color_to_selection(self, color: str) -> None:
        task_id = self.selected_task_id()
        if task_id is None:
            self.statusBar().showMessage("Выберите заявку, чтобы задать цвет")
            return
        try:
            self.service.update_task(task_id, UpdateTaskRequest(color=color))
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.reload_current_tab()

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
        QShortcut(QKeySequence.StandardKey.Find, self, activated=self.focus_search)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.add_task)
        QShortcut(QKeySequence("F5"), self, activated=self.reload_current_tab)

    def focus_search(self) -> None:
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    # --- data loading ---

    def reload_directories(self) -> None:
        current_id = self.current_directory_id()
        self.tabs.blockSignals(True)
        self.tabs.clear()
        for directory in self.service.list_directories():
            table = self._make_table()
            self.tabs.addTab(table, directory.name)
            self.tabs.tabBar().setTabData(self.tabs.count() - 1, directory.id)
            self._fill_table(table, directory)
        self.tabs.blockSignals(False)

        if current_id is not None:
            for i in range(self.tabs.count()):
                if self.tabs.tabBar().tabData(i) == current_id:
                    self.tabs.setCurrentIndex(i)
                    break
        elif self.tabs.count():
            self.tabs.setCurrentIndex(0)

    def reload_current_tab(self) -> None:
        idx = self.tabs.currentIndex()
        if idx < 0:
            return
        directory_id = self.tabs.tabBar().tabData(idx)
        directory = next(
            (d for d in self.service.list_directories() if d.id == directory_id),
            None,
        )
        if directory is None:
            self.reload_directories()
            return
        table = self.tabs.widget(idx)
        assert isinstance(table, QTableWidget)
        self._fill_table(table, directory)

    def _make_table(self) -> QTableWidget:
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Номер", "Срок", "Описание"])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(False)
        table.setSortingEnabled(True)
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(COL_NUMBER, Qt.SortOrder.AscendingOrder)
        table.verticalHeader().setVisible(False)
        table.doubleClicked.connect(self.edit_selected_task)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(
            lambda pos, t=table: self._show_context_menu(t, pos)
        )
        return table

    def _fill_table(self, table: QTableWidget, directory: Directory) -> None:
        query = self._search_query or None
        tasks = self.service.list_tasks(
            directory.id,  # type: ignore[arg-type]
            only_hidden=self._show_hidden,
            query=query,
        )

        table.setSortingEnabled(False)
        table.setRowCount(0)
        today = date.today()
        for task in tasks:
            row = table.rowCount()
            table.insertRow(row)

            number_item = SortableItem(task.number)
            number_item.setData(TASK_ID_ROLE, task.id)
            number_item.setData(SORT_ROLE, task.number.casefold())
            table.setItem(row, COL_NUMBER, number_item)

            date_text = task.date_end.strftime("%d.%m.%Y") if task.date_end else ""
            date_item = SortableItem(date_text)
            date_item.setData(
                SORT_ROLE,
                task.date_end.toordinal() if task.date_end else 0,
            )
            table.setItem(row, COL_DATE, date_item)

            desc_item = SortableItem(task.description)
            desc_item.setData(SORT_ROLE, task.description.casefold())
            table.setItem(row, COL_DESCRIPTION, desc_item)

            bg = QColor(task.color)
            for col in (COL_NUMBER, COL_DATE, COL_DESCRIPTION):
                item = table.item(row, col)
                if item:
                    item.setBackground(bg)

            if self.settings.highlight_warnings and is_deadline_warning(
                task.date_end,
                today=today,
                lead_days=self.settings.warning_lead_days,
            ):
                warn = QColor(self.settings.warning_color)
                for col in (COL_NUMBER, COL_DATE, COL_DESCRIPTION):
                    item = table.item(row, col)
                    if item:
                        item.setForeground(warn)

        table.setSortingEnabled(True)
        header = table.horizontalHeader()
        table.sortItems(header.sortIndicatorSection(), header.sortIndicatorOrder())
        mode = "скрытых" if self._show_hidden else "заявок"
        self.statusBar().showMessage(f"{directory.name}: {len(tasks)} {mode}")

    # --- selection helpers ---

    def current_directory_id(self) -> int | None:
        idx = self.tabs.currentIndex()
        if idx < 0:
            return None
        data = self.tabs.tabBar().tabData(idx)
        return int(data) if data is not None else None

    def current_table(self) -> QTableWidget | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, QTableWidget) else None

    def selected_task_id(self) -> int | None:
        table = self.current_table()
        if table is None:
            return None
        row = table.currentRow()
        if row < 0:
            return None
        item = table.item(row, 0)
        if item is None:
            return None
        value = item.data(TASK_ID_ROLE)
        return int(value) if value is not None else None

    # --- actions ---

    def add_directory(self) -> None:
        dialog = DirectoryDialog(self, title="Новая директория")
        if dialog.exec() != DirectoryDialog.DialogCode.Accepted:
            return
        try:
            self.service.create_directory(dialog.directory_name)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.reload_directories()

    def rename_current_directory(self) -> None:
        directory_id = self.current_directory_id()
        if directory_id is None:
            return
        directory = next(
            (d for d in self.service.list_directories() if d.id == directory_id),
            None,
        )
        if directory is None:
            return
        dialog = DirectoryDialog(
            self,
            name=directory.name,
            title="Изменить директорию",
        )
        if dialog.exec() != DirectoryDialog.DialogCode.Accepted:
            return
        try:
            self.service.rename_directory(directory_id, dialog.directory_name)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.reload_directories()

    def open_current_directory_folder(self) -> None:
        directory_id = self.current_directory_id()
        if directory_id is None:
            return
        try:
            path = self.service.directory_folder_path(directory_id)
            open_target(str(path))
        except (ServiceError, PlatformOpenError) as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))

    def delete_current_directory(self) -> None:
        directory_id = self.current_directory_id()
        if directory_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Удаление",
            "Удалить директорию? Активные заявки должны быть заархивированы заранее.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_directory(directory_id, remove_folder=True)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.reload_directories()

    def add_task(self) -> None:
        directory_id = self.current_directory_id()
        if directory_id is None:
            QMessageBox.information(self, "Уведомление", "Сначала создайте директорию")
            return
        dialog = TaskDialog(self.settings, self, title="Новая заявка")
        if dialog.exec() != TaskDialog.DialogCode.Accepted:
            return
        try:
            self.service.create_task(
                CreateTaskRequest(
                    directory_id=directory_id,
                    number=dialog.number,
                    description=dialog.description,
                    date_end=dialog.date_end,
                    color="#ffffff",
                    hidden=dialog.hidden,
                    by_template=dialog.by_template,
                    links=dialog.links,
                )
            )
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.reload_current_tab()

    def edit_selected_task(self) -> None:
        task_id = self.selected_task_id()
        if task_id is None:
            QMessageBox.information(self, "Уведомление", "Выберите заявку")
            return
        try:
            task = self.service.get_task(task_id)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        dialog = TaskDialog(
            self.settings,
            self,
            task=task,
            title="Изменить заявку",
            allow_template=False,
        )
        if dialog.exec() != TaskDialog.DialogCode.Accepted:
            return
        try:
            self.service.update_task(
                task_id,
                UpdateTaskRequest(
                    number=dialog.number,
                    description=dialog.description,
                    date_end=dialog.date_end,
                    clear_date_end=dialog.date_end is None,
                    hidden=dialog.hidden,
                    links=dialog.links,
                ),
            )
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.reload_current_tab()

    def archive_selected_task(self) -> None:
        task_id = self.selected_task_id()
        if task_id is None:
            QMessageBox.information(self, "Уведомление", "Выберите заявку")
            return
        answer = QMessageBox.question(
            self,
            "Архив",
            "Перед переносом закройте файлы заявки. Продолжить?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.archive_task(task_id)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.reload_current_tab()

    def delete_selected_task(self) -> None:
        task_id = self.selected_task_id()
        if task_id is None:
            QMessageBox.information(self, "Уведомление", "Выберите заявку")
            return
        answer = QMessageBox.question(
            self,
            "Удаление",
            "Удалить заявку и её папку? Действие необратимо.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_task(task_id)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.reload_current_tab()

    def open_selected_folder(self) -> None:
        task_id = self.selected_task_id()
        if task_id is None:
            QMessageBox.information(self, "Уведомление", "Выберите заявку")
            return
        try:
            path = self.service.task_folder_path(task_id)
            open_target(str(path))
        except (ServiceError, PlatformOpenError) as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self.settings_store, self)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return
        self.settings = dialog.settings
        self.service.settings = self.settings
        self.service.fs.settings = self.settings
        self._rebuild_color_palette()
        self.reload_directories()

    def _on_search_changed(self, text: str) -> None:
        self._search_query = text.strip()
        self.reload_current_tab()

    def _on_hidden_toggled(self, checked: bool) -> None:
        self._show_hidden = checked
        self.reload_current_tab()

    def _on_tab_changed(self, _index: int) -> None:
        self.reload_current_tab()

    def _show_tab_context_menu(self, pos) -> None:
        tab_bar = self.tabs.tabBar()
        index = tab_bar.tabAt(pos)
        if index < 0:
            return
        self.tabs.setCurrentIndex(index)
        menu = QMenu(self)
        menu.addAction("Изменить", self.rename_current_directory)
        menu.addAction("Открыть папку", self.open_current_directory_folder)
        menu.addAction("Удалить", self.delete_current_directory)
        menu.exec(tab_bar.mapToGlobal(pos))

    def _show_context_menu(self, table: QTableWidget, pos) -> None:
        index = table.indexAt(pos)
        if index.isValid():
            table.selectRow(index.row())
        task_id = self.selected_task_id()
        menu = QMenu(self)
        menu.addAction("Изменить", self.edit_selected_task)
        menu.addAction("Открыть папку", self.open_selected_folder)
        menu.addAction("В архив", self.archive_selected_task)
        menu.addAction("Удалить", self.delete_selected_task)

        if task_id is not None:
            try:
                task = self.service.get_task(task_id)
            except ServiceError:
                task = None
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

    def _check_missing_folders(self) -> None:
        missing = self.service.check_missing_folders()
        if not missing:
            return
        lines = [
            f"• {directory.name} / {task.number} ({task.folder_name})"
            for directory, task in missing[:20]
        ]
        extra = ""
        if len(missing) > 20:
            extra = f"\n… и ещё {len(missing) - 20}"
        QMessageBox.warning(
            self,
            "Папки не найдены",
            "На диске отсутствуют папки для заявок:\n"
            + "\n".join(lines)
            + extra
            + "\n\nМетаданные в БД сохранены; восстановите папки или удалите записи.",
        )
