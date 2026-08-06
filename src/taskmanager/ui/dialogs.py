from __future__ import annotations

from collections.abc import Callable
from datetime import date

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QDesktopServices,
    QFont,
    QKeySequence,
    QMouseEvent,
    QTextCharFormat,
    QTextCursor,
    QTextListFormat,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from taskmanager.domain import (
    PRIORITY_DEFAULT,
    PRIORITY_MAX,
    PRIORITY_MIN,
    Project,
    Task,
    clamp_priority,
    contrast_foreground,
    priority_color_hex,
)
from taskmanager.services.settings_service import Settings


class ProjectDialog(QDialog):
    def __init__(self, parent=None, *, name: str = "", title: str = "Проект") -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(name)
        form.addRow("Имя", self.name_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Введите имя проекта")
            return
        self.accept()

    @property
    def project_name(self) -> str:
        return self.name_edit.text().strip()


# Backward-compatible alias
DirectoryDialog = ProjectDialog


class _LinkAwareTextEdit(QTextEdit):
    """QTextEdit that opens anchors on Ctrl+click; plain click selects as usual."""

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            href = self.anchorAt(event.position().toPoint())
            if href:
                QDesktopServices.openUrl(QUrl(href))
                event.accept()
                return
        super().mousePressEvent(event)


class RichTextEditDialog(QDialog):
    """Modal rich-text editor for description/comment HTML fields."""

    def __init__(
        self,
        parent=None,
        *,
        title: str = "Редактор",
        html: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(676, 468)
        layout = QVBoxLayout(self)

        toolbar = QToolBar()
        self.editor = _LinkAwareTextEdit()
        self.editor.setAcceptRichText(True)
        if html:
            self.editor.setHtml(html)

        self._act_bold = QAction("Ж", self)
        self._act_bold.setCheckable(True)
        self._act_bold.setShortcut(QKeySequence.StandardKey.Bold)
        self._act_bold.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._act_bold.triggered.connect(self._toggle_bold)
        self._act_italic = QAction("К", self)
        self._act_italic.setCheckable(True)
        self._act_italic.setShortcut(QKeySequence.StandardKey.Italic)
        self._act_italic.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._act_italic.triggered.connect(self._toggle_italic)
        self._act_underline = QAction("Ч", self)
        self._act_underline.setCheckable(True)
        self._act_underline.setShortcut(QKeySequence.StandardKey.Underline)
        self._act_underline.setShortcutContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self._act_underline.triggered.connect(self._toggle_underline)
        self._act_bullet = QAction("•", self)
        self._act_bullet.setCheckable(True)
        self._act_bullet.setToolTip("Маркированный список")
        self._act_bullet.triggered.connect(self._toggle_bullet_list)
        self._act_numbered = QAction("1.", self)
        self._act_numbered.setCheckable(True)
        self._act_numbered.setToolTip("Нумерованный список")
        self._act_numbered.triggered.connect(self._toggle_numbered_list)
        self._act_link = QAction("Ссылка", self)
        self._act_link.setCheckable(False)
        self._act_link.triggered.connect(self._insert_link)
        toolbar.addAction(self._act_bold)
        toolbar.addAction(self._act_italic)
        toolbar.addAction(self._act_underline)
        toolbar.addAction(self._act_bullet)
        toolbar.addAction(self._act_numbered)
        toolbar.addAction(self._act_link)
        self.addAction(self._act_bold)
        self.addAction(self._act_italic)
        self.addAction(self._act_underline)
        layout.addWidget(toolbar)
        layout.addWidget(self.editor)

        self.editor.currentCharFormatChanged.connect(self._sync_format_actions)
        self.editor.cursorPositionChanged.connect(self._sync_format_actions)
        self._sync_format_actions()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _sync_format_actions(self, *_args) -> None:
        fmt = self.editor.currentCharFormat()
        for action, checked in (
            (self._act_bold, fmt.fontWeight() >= int(QFont.Weight.Bold)),
            (self._act_italic, fmt.fontItalic()),
            (self._act_underline, fmt.fontUnderline()),
        ):
            action.blockSignals(True)
            action.setChecked(checked)
            action.blockSignals(False)

        lst = self.editor.textCursor().currentList()
        style = lst.format().style() if lst is not None else None
        for action, checked in (
            (self._act_bullet, style == QTextListFormat.Style.ListDisc),
            (self._act_numbered, style == QTextListFormat.Style.ListDecimal),
        ):
            action.blockSignals(True)
            action.setChecked(checked)
            action.blockSignals(False)

    def _toggle_bold(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontWeight(
            QFont.Weight.Bold if checked else QFont.Weight.Normal
        )
        self.editor.mergeCurrentCharFormat(fmt)

    def _toggle_italic(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(checked)
        self.editor.mergeCurrentCharFormat(fmt)

    def _toggle_underline(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(checked)
        self.editor.mergeCurrentCharFormat(fmt)

    def _toggle_bullet_list(self, checked: bool) -> None:
        self._apply_list_style(
            QTextListFormat.Style.ListDisc if checked else None
        )

    def _toggle_numbered_list(self, checked: bool) -> None:
        self._apply_list_style(
            QTextListFormat.Style.ListDecimal if checked else None
        )

    def _apply_list_style(self, style: QTextListFormat.Style | None) -> None:
        cursor = self.editor.textCursor()
        if style is not None:
            cursor.createList(style)
            self.editor.setTextCursor(cursor)
        else:
            self._remove_list_from_selection(cursor)
        self._sync_format_actions()

    def _remove_list_from_selection(self, cursor: QTextCursor) -> None:
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        cursor.beginEditBlock()
        block = self.editor.document().findBlock(start)
        while block.isValid() and block.position() <= end:
            block_cursor = QTextCursor(block)
            lst = block_cursor.currentList()
            if lst is not None:
                lst.remove(block)
            next_block = block.next()
            if not next_block.isValid() or next_block.position() > end:
                break
            block = next_block
        cursor.endEditBlock()

    def _insert_link(self) -> None:
        url, ok = QInputDialog.getText(self, "Ссылка", "URL:")
        if not ok or not url.strip():
            return
        cursor = self.editor.textCursor()
        selected = cursor.selectedText() or url.strip()
        fmt = QTextCharFormat()
        fmt.setAnchor(True)
        fmt.setAnchorHref(url.strip())
        fmt.setForeground(QColor("#0d9488"))
        fmt.setFontUnderline(True)
        cursor.insertText(selected, fmt)

    @property
    def html(self) -> str:
        return self.editor.toHtml()


class HtmlEditRow(QWidget):
    """Editable raw-HTML line + «…» button opening RichTextEditDialog."""

    def __init__(self, parent=None, *, title: str = "Текст", html: str = "") -> None:
        super().__init__(parent)
        self._title = title
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit(html or "")
        self.edit.setPlaceholderText("HTML…")
        btn = QPushButton("…")
        btn.setObjectName("secondaryButton")
        btn.setFixedWidth(36)
        btn.setToolTip("Редактировать")
        btn.clicked.connect(self._edit)
        layout.addWidget(self.edit)
        layout.addWidget(btn)

    def _edit(self) -> None:
        dialog = RichTextEditDialog(self, title=self._title, html=self.edit.text())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.edit.setText(dialog.html)

    @property
    def html(self) -> str:
        return self.edit.text()

    @html.setter
    def html(self, value: str) -> None:
        self.edit.setText(value or "")


# Backward-compatible alias
HtmlPreviewRow = HtmlEditRow


class TaskDialog(QDialog):
    def __init__(
        self,
        settings: Settings,
        parent=None,
        *,
        task: Task | None = None,
        title: str = "Заявка",
        allow_template: bool = True,
        create_folder_default: bool | None = None,
        folder_validator: Callable[["TaskDialog"], str | None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(560)
        self._settings = settings
        self._task = task
        self._folder_validator = folder_validator

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.number_edit = QLineEdit(task.number if task else "")
        form.addRow("Номер", self.number_edit)

        self.description_row = HtmlEditRow(
            title="Описание",
            html=task.description if task else "",
        )
        form.addRow("Описание", self.description_row)

        self.comment_row = HtmlEditRow(
            title="Комментарий",
            html=task.comment if task else "",
        )
        form.addRow("Комментарий", self.comment_row)

        self.priority_combo = QComboBox()
        for value in range(PRIORITY_MIN, PRIORITY_MAX + 1):
            self.priority_combo.addItem(str(value), value)
            bg = priority_color_hex(value)
            self.priority_combo.setItemData(
                value, QBrush(QColor(bg)), Qt.ItemDataRole.BackgroundRole
            )
            self.priority_combo.setItemData(
                value,
                QBrush(QColor(contrast_foreground(bg))),
                Qt.ItemDataRole.ForegroundRole,
            )
        initial_priority = (
            clamp_priority(task.priority) if task else PRIORITY_DEFAULT
        )
        self.priority_combo.setCurrentIndex(initial_priority)
        self.priority_combo.currentIndexChanged.connect(self._sync_priority_combo_color)
        self._sync_priority_combo_color()
        form.addRow("Приоритет", self.priority_combo)

        self.date_end_edit = QDateEdit()
        self.date_end_edit.setCalendarPopup(True)
        self.date_end_edit.setDisplayFormat("dd.MM.yyyy")
        self.has_date_end = QCheckBox("Указать срок")
        if task and task.date_end:
            self.has_date_end.setChecked(True)
            self.date_end_edit.setDate(
                QDate(task.date_end.year, task.date_end.month, task.date_end.day)
            )
        else:
            self.has_date_end.setChecked(False)
            self.date_end_edit.setDate(QDate.currentDate())
        self.date_end_edit.setEnabled(self.has_date_end.isChecked())
        self.has_date_end.toggled.connect(self.date_end_edit.setEnabled)
        date_row = QHBoxLayout()
        date_row.addWidget(self.has_date_end)
        date_row.addWidget(self.date_end_edit)
        form.addRow("Срок", date_row)

        self.hidden_cb = QCheckBox("Скрытая")
        self.hidden_cb.setChecked(bool(task and task.hidden))
        form.addRow(self.hidden_cb)

        folder_default = (
            settings.create_task_folder
            if create_folder_default is None
            else create_folder_default
        )
        self.create_folder_cb = QCheckBox("Создать папку на диске")
        self.create_folder_cb.setChecked(folder_default)
        self.template_cb = QCheckBox(
            f"Создать из шаблона («{settings.template_name}»)"
        )
        self.template_cb.setChecked(False)
        self.notes_cb = QCheckBox("Создать файл заметок (Notes.txt)")
        self.notes_cb.setChecked(settings.create_notes_file)

        if allow_template and task is None:
            form.addRow(self.create_folder_cb)
            form.addRow(self.template_cb)
            form.addRow(self.notes_cb)
            self.create_folder_cb.toggled.connect(self._sync_folder_options)
            self.template_cb.toggled.connect(self._on_template_toggled)
            self._sync_folder_options(self.create_folder_cb.isChecked())
        else:
            self.create_folder_cb.setVisible(False)
            self.template_cb.setVisible(False)
            self.notes_cb.setVisible(False)

        if task is not None:
            if task.created_at:
                created = QLabel(
                    task.created_at.strftime("%d.%m.%Y %H:%M:%S")
                )
                form.addRow("Создана", created)
            folder_state = (
                "есть (флаг)"
                if task.has_folder
                else "нет (только БД)"
            )
            hint = QLabel(
                f"Папка на диске: {task.folder_name} — {folder_state}"
            )
            hint.setWordWrap(True)
            hint.setStyleSheet("color: #64748b;")
            form.addRow(hint)

        layout.addLayout(form)

        layout.addWidget(QLabel("Ссылки"))
        self.links_table = QTableWidget(0, 2)
        self.links_table.setHorizontalHeaderLabels(["Имя", "URL / путь"])
        self.links_table.horizontalHeader().setStretchLastSection(True)
        self.links_table.setMinimumHeight(120)
        if task and task.links:
            for link in task.links:
                self._add_link_row(link.name, link.target)
        layout.addWidget(self.links_table)

        link_btns = QHBoxLayout()
        add_link = QPushButton("Добавить ссылку")
        add_link.setObjectName("secondaryButton")
        add_link.clicked.connect(lambda: self._add_link_row("", ""))
        remove_link = QPushButton("Удалить ссылку")
        remove_link.setObjectName("secondaryButton")
        remove_link.clicked.connect(self._remove_link_row)
        link_btns.addWidget(add_link)
        link_btns.addWidget(remove_link)
        link_btns.addStretch()
        layout.addLayout(link_btns)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_template_toggled(self, checked: bool) -> None:
        if checked:
            self.create_folder_cb.setChecked(True)
        self._sync_folder_options(self.create_folder_cb.isChecked())

    def _sync_folder_options(self, has_folder: bool) -> None:
        self.template_cb.setEnabled(has_folder)
        self.notes_cb.setEnabled(has_folder)
        if not has_folder:
            self.template_cb.setChecked(False)
            self.notes_cb.setChecked(False)

    def _sync_priority_combo_color(self) -> None:
        color = priority_color_hex(self.priority)
        fg = contrast_foreground(color)
        self.priority_combo.setStyleSheet(
            f"QComboBox {{ background-color: {color}; color: {fg}; }}"
        )

    def _add_link_row(self, name: str, target: str) -> None:
        row = self.links_table.rowCount()
        self.links_table.insertRow(row)
        self.links_table.setItem(row, 0, QTableWidgetItem(name))
        self.links_table.setItem(row, 1, QTableWidgetItem(target))

    def _remove_link_row(self) -> None:
        row = self.links_table.currentRow()
        if row >= 0:
            self.links_table.removeRow(row)

    def _accept(self) -> None:
        if not self.number_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Введите номер заявки")
            return
        if self._folder_validator is not None:
            error = self._folder_validator(self)
            if error:
                QMessageBox.warning(self, "Ошибка", error)
                return
        self.accept()

    @property
    def number(self) -> str:
        return self.number_edit.text().strip()

    @property
    def description(self) -> str:
        return self.description_row.html

    @property
    def comment(self) -> str:
        return self.comment_row.html

    @property
    def priority(self) -> int:
        return clamp_priority(self.priority_combo.currentData())

    @property
    def date_end(self) -> date | None:
        if not self.has_date_end.isChecked():
            return None
        qd = self.date_end_edit.date()
        return date(qd.year(), qd.month(), qd.day())

    @property
    def hidden(self) -> bool:
        return self.hidden_cb.isChecked()

    @property
    def by_template(self) -> bool:
        return self.template_cb.isChecked()

    @property
    def create_notes_file(self) -> bool:
        return self.notes_cb.isChecked()

    @property
    def create_folder(self) -> bool:
        if self._task is not None:
            return self._task.has_folder
        return self.create_folder_cb.isChecked()

    @property
    def links(self) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        for row in range(self.links_table.rowCount()):
            name_item = self.links_table.item(row, 0)
            target_item = self.links_table.item(row, 1)
            name = name_item.text().strip() if name_item else ""
            target = target_item.text().strip() if target_item else ""
            if name and target:
                result.append((name, target))
        return result


class MissingFoldersDialog(QDialog):
    """Startup warning listing missing folders with recreate / clear actions."""

    def __init__(
        self,
        missing: list[tuple[Project, Task]],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Папки не найдены")
        self.setMinimumWidth(480)
        self._missing = list(missing)
        self.recreate_ids: list[int] = []
        self.clear_ids: list[int] = []

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "У заявок с флагом папки отсутствуют каталоги на диске.\n"
                "Выберите действие для каждой или для всех:"
            )
        )
        self.list_widget = QListWidget()
        for project, task in missing:
            item = QListWidgetItem(
                f"{project.name} / {task.number} ({task.folder_name})"
            )
            item.setData(Qt.ItemDataRole.UserRole, task.id)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        row = QHBoxLayout()
        recreate_sel = QPushButton("Создать заново")
        recreate_sel.setObjectName("secondaryButton")
        recreate_sel.clicked.connect(self._recreate_selected)
        clear_sel = QPushButton("Считать без папки")
        clear_sel.setObjectName("secondaryButton")
        clear_sel.clicked.connect(self._clear_selected)
        recreate_all = QPushButton("Создать все")
        recreate_all.clicked.connect(self._recreate_all)
        clear_all = QPushButton("Все без папки")
        clear_all.setObjectName("secondaryButton")
        clear_all.clicked.connect(self._clear_all)
        row.addWidget(recreate_sel)
        row.addWidget(clear_sel)
        row.addWidget(recreate_all)
        row.addWidget(clear_all)
        layout.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn:
            close_btn.clicked.connect(self.accept)
        layout.addWidget(buttons)

    def _selected_ids(self) -> list[int]:
        ids: list[int] = []
        for item in self.list_widget.selectedItems():
            value = item.data(Qt.ItemDataRole.UserRole)
            if value is not None:
                ids.append(int(value))
        return ids

    def _all_ids(self) -> list[int]:
        ids: list[int] = []
        for i in range(self.list_widget.count()):
            value = self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            if value is not None:
                ids.append(int(value))
        return ids

    def _recreate_selected(self) -> None:
        ids = self._selected_ids() or self._all_ids()
        self.recreate_ids = ids
        self.clear_ids = []
        self.accept()

    def _clear_selected(self) -> None:
        ids = self._selected_ids() or self._all_ids()
        self.clear_ids = ids
        self.recreate_ids = []
        self.accept()

    def _recreate_all(self) -> None:
        self.recreate_ids = self._all_ids()
        self.clear_ids = []
        self.accept()

    def _clear_all(self) -> None:
        self.clear_ids = self._all_ids()
        self.recreate_ids = []
        self.accept()


class ExcelExportDialog(QDialog):
    def __init__(self, projects: list[Project], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Экспорт в Excel")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Проекты:"))
        self.list_widget = QListWidget()
        for project in projects:
            item = QListWidgetItem(project.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, project.id)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        self.hidden_cb = QCheckBox("Включить скрытые")
        self.archive_cb = QCheckBox("Включить архив")
        layout.addWidget(self.hidden_cb)
        layout.addWidget(self.archive_cb)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        if not self.selected_project_ids:
            QMessageBox.warning(self, "Ошибка", "Выберите хотя бы один проект")
            return
        self.accept()

    @property
    def selected_project_ids(self) -> list[int]:
        ids: list[int] = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                value = item.data(Qt.ItemDataRole.UserRole)
                if value is not None:
                    ids.append(int(value))
        return ids

    @property
    def include_hidden(self) -> bool:
        return self.hidden_cb.isChecked()

    @property
    def include_archived(self) -> bool:
        return self.archive_cb.isChecked()
