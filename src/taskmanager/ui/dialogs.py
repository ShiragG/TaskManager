from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from taskmanager.domain import Task
from taskmanager.services.settings_service import Settings


class DirectoryDialog(QDialog):
    def __init__(self, parent=None, *, name: str = "", title: str = "Директория") -> None:
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
            QMessageBox.warning(self, "Ошибка", "Введите имя директории")
            return
        self.accept()

    @property
    def directory_name(self) -> str:
        return self.name_edit.text().strip()


class TaskDialog(QDialog):
    def __init__(
        self,
        settings: Settings,
        parent=None,
        *,
        task: Task | None = None,
        title: str = "Заявка",
        allow_template: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(520)
        self._settings = settings

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.number_edit = QLineEdit(task.number if task else "")
        form.addRow("Номер", self.number_edit)

        self.description_edit = QLineEdit(task.description if task else "")
        form.addRow("Описание", self.description_edit)

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

        self.template_cb = QCheckBox(
            f"Создать из шаблона («{settings.template_name}»)"
        )
        self.template_cb.setChecked(False)
        if allow_template and task is None:
            form.addRow(self.template_cb)
        else:
            self.template_cb.setVisible(False)

        if task is not None:
            hint = QLabel(f"Папка на диске: {task.folder_name}")
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
        self.accept()

    @property
    def number(self) -> str:
        return self.number_edit.text().strip()

    @property
    def description(self) -> str:
        return self.description_edit.text().strip()

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
