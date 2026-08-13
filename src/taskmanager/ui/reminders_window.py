"""Calendar window and Event create/edit/notify dialogs."""

from __future__ import annotations

import calendar
from datetime import date, datetime, time

from PySide6.QtCore import QDate, QTime, QUrl, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from taskmanager.domain import (
    ReminderRule,
    ReminderSeries,
    Task,
    WEEKDAY_LABELS,
    html_to_plain,
    occurrences_in_range,
    truncate_plain,
)
from taskmanager.infrastructure.platform_open import PlatformOpenError, open_target
from taskmanager.services.settings_service import (
    DEFAULT_SNOOZE_MINUTES,
    SNOOZE_LABELS,
    SNOOZE_MINUTES,
    parse_snooze_minutes,
)
from taskmanager.services.task_service import ServiceError, TaskService
from taskmanager.ui.dialogs import HtmlEditRow

_MONTH_NAMES = (
    "",
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
)


def _open_event_link(parent: QWidget, url: QUrl) -> None:
    target = url.toString()
    if not target:
        return
    try:
        open_target(target)
    except PlatformOpenError as exc:
        QMessageBox.warning(parent, "Предупреждение", str(exc))


def _qdate_for_month_day(day: int, ref: date) -> QDate:
    year, month = ref.year, ref.month
    for _ in range(24):
        try:
            chosen = date(year, month, day)
            return QDate(chosen.year, chosen.month, chosen.day)
        except ValueError:
            month += 1
            if month == 13:
                month = 1
                year += 1
    return QDate(ref.year, ref.month, min(max(day, 1), 28))


class ReminderEditDialog(QDialog):
    def __init__(
        self,
        service: TaskService,
        parent=None,
        *,
        task: Task | None = None,
        series: ReminderSeries | None = None,
        initial_date: date | None = None,
        require_task_pick: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Событие")
        self.setMinimumWidth(480)
        self._service = service
        self._task = task
        self._series_id = series.id if series is not None else None
        self._picked_task_id: int | None = (
            series.task_id if series is not None else (task.id if task else None)
        )

        layout = QVBoxLayout(self)
        self._form = QFormLayout()

        self.task_search = QLineEdit()
        self.task_list = QListWidget()
        self.clear_task_btn = QPushButton("Очистить")
        self.clear_task_btn.setObjectName("secondaryButton")
        self._task_choices: list[tuple[int, str, str, str]] = []
        self.task_search.setPlaceholderText("Номер, описание или проект")
        for project in service.list_projects():
            visible = service.list_tasks(
                project.id, only_hidden=False  # type: ignore[arg-type]
            )
            hidden = service.list_tasks(
                project.id, only_hidden=True  # type: ignore[arg-type]
            )
            for item in (*visible, *hidden):
                if item.id is None:
                    continue
                label = f"{project.name} / {item.number}"
                self._task_choices.append(
                    (
                        item.id,
                        label,
                        item.number,
                        f"{label} {item.number} {item.description_plain}",
                    )
                )
        picker = QWidget()
        picker_layout = QVBoxLayout(picker)
        picker_layout.setContentsMargins(0, 0, 0, 0)
        search_row = QHBoxLayout()
        search_row.addWidget(self.task_search, stretch=1)
        search_row.addWidget(self.clear_task_btn)
        picker_layout.addLayout(search_row)
        self.task_list.setMinimumHeight(120)
        picker_layout.addWidget(self.task_list)
        self.task_search.textChanged.connect(self._filter_task_choices)
        self.task_list.itemSelectionChanged.connect(self._on_task_picked)
        self.clear_task_btn.clicked.connect(self._clear_task_pick)
        self._form.addRow("Заявка", picker)
        self._filter_task_choices("")
        self._sync_search_from_pick()

        self.text_edit = HtmlEditRow(title="Текст", html="")
        self._form.addRow("Текст", self.text_edit)

        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime(9, 0))
        self._form.addRow("Время", self.time_edit)

        self.rule_combo = QComboBox()
        self.rule_combo.addItem("Разово", ReminderRule.ONCE.value)
        self.rule_combo.addItem("Еженедельно", ReminderRule.WEEKLY.value)
        self.rule_combo.addItem("Ежемесячно", ReminderRule.MONTHLY.value)
        self.rule_combo.currentIndexChanged.connect(self._sync_rule_fields)
        self._form.addRow("Повтор", self.rule_combo)

        self.once_date = QDateEdit()
        self.once_date.setCalendarPopup(True)
        self.once_date.setDisplayFormat("dd.MM.yyyy")
        start = initial_date or date.today()
        self.once_date.setDate(QDate(start.year, start.month, start.day))
        self._form.addRow("Дата", self.once_date)

        weekday_row = QHBoxLayout()
        self.weekday_boxes: list[QCheckBox] = []
        for label_text in WEEKDAY_LABELS:
            box = QCheckBox(label_text)
            self.weekday_boxes.append(box)
            weekday_row.addWidget(box)
        weekday_row.addStretch()
        self.weekday_host = QWidget()
        self.weekday_host.setLayout(weekday_row)
        self._form.addRow("Дни недели", self.weekday_host)

        layout.addLayout(self._form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if series is not None:
            self._load_series(series)
        self._sync_rule_fields()

    def _load_series(self, series: ReminderSeries) -> None:
        self.text_edit.html = series.text
        clock = series.time_of_day
        self.time_edit.setTime(QTime(clock.hour, clock.minute))
        idx = self.rule_combo.findData(series.rule.value)
        if idx >= 0:
            self.rule_combo.setCurrentIndex(idx)
        if series.once_date is not None:
            day = series.once_date
            self.once_date.setDate(QDate(day.year, day.month, day.day))
        elif series.month_day is not None:
            self.once_date.setDate(_qdate_for_month_day(series.month_day, date.today()))
        for i, box in enumerate(self.weekday_boxes):
            box.setChecked(i in series.weekdays)

    def _set_row_visible(self, widget: QWidget, visible: bool) -> None:
        widget.setVisible(visible)
        label = self._form.labelForField(widget)
        if label is not None:
            label.setVisible(visible)

    def _filter_task_choices(self, query: str) -> None:
        needle = query.casefold().strip()
        self.task_list.blockSignals(True)
        self.task_list.clear()
        selected_row = -1
        for task_id, label, number, haystack in self._task_choices:
            if needle and needle not in haystack.casefold() and needle not in number.casefold():
                continue
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, task_id)
            self.task_list.addItem(item)
            if self._picked_task_id is not None and task_id == self._picked_task_id:
                selected_row = self.task_list.count() - 1
        if selected_row >= 0:
            self.task_list.setCurrentRow(selected_row)
        self.task_list.blockSignals(False)

    def _sync_search_from_pick(self) -> None:
        if self._picked_task_id is None:
            return
        for task_id, label, _number, _haystack in self._task_choices:
            if task_id == self._picked_task_id:
                self.task_search.blockSignals(True)
                self.task_search.setText(label)
                self.task_search.blockSignals(False)
                return

    def _clear_task_pick(self) -> None:
        self._picked_task_id = None
        self.task_search.blockSignals(True)
        self.task_search.clear()
        self.task_search.blockSignals(False)
        self._filter_task_choices("")

    def _on_task_picked(self) -> None:
        item = self.task_list.currentItem()
        if item is None:
            return
        task_id = item.data(Qt.ItemDataRole.UserRole)
        if task_id is not None:
            self._picked_task_id = int(task_id)
        self.task_search.blockSignals(True)
        self.task_search.setText(item.text())
        self.task_search.blockSignals(False)

    def _sync_rule_fields(self) -> None:
        rule = self.rule_combo.currentData()
        self._set_row_visible(
            self.once_date,
            rule in {ReminderRule.ONCE.value, ReminderRule.MONTHLY.value},
        )
        self._set_row_visible(self.weekday_host, rule == ReminderRule.WEEKLY.value)

    def _accept(self) -> None:
        if self.rule_combo.currentData() == ReminderRule.WEEKLY.value:
            if not any(box.isChecked() for box in self.weekday_boxes):
                QMessageBox.warning(self, "Ошибка", "Выберите хотя бы один день недели")
                return
        self.accept()

    def save_to_service(self) -> ReminderSeries:
        kwargs = dict(
            text=self.reminder_text,
            time_of_day=self.time_of_day,
            rule=self.rule,
            once_date=self.once_date_value,
            weekdays=self.weekdays,
            month_day=self.month_day_value,
        )
        if self._series_id is None:
            return self._service.create_reminder(self.task_id, **kwargs)
        return self._service.update_reminder(
            self._series_id, task_id=self.task_id, **kwargs
        )

    @property
    def task_id(self) -> int | None:
        return self._picked_task_id

    @property
    def reminder_text(self) -> str:
        return self.text_edit.html.strip()

    @property
    def time_of_day(self) -> time:
        qt = self.time_edit.time()
        return time(qt.hour(), qt.minute())

    @property
    def rule(self) -> ReminderRule:
        return ReminderRule(self.rule_combo.currentData())

    @property
    def once_date_value(self) -> date | None:
        if self.rule != ReminderRule.ONCE:
            return None
        qd = self.once_date.date()
        return date(qd.year(), qd.month(), qd.day())

    @property
    def weekdays(self) -> tuple[int, ...]:
        if self.rule != ReminderRule.WEEKLY:
            return ()
        return tuple(i for i, box in enumerate(self.weekday_boxes) if box.isChecked())

    @property
    def month_day_value(self) -> int | None:
        if self.rule != ReminderRule.MONTHLY:
            return None
        return int(self.once_date.date().day())


def format_reminder_series(series: ReminderSeries) -> str:
    clock = series.time_of_day.strftime("%H:%M")
    text = html_to_plain(series.text) or "—"
    if series.rule == ReminderRule.ONCE:
        day = series.once_date.strftime("%d.%m.%Y") if series.once_date else ""
        return f"{clock}  {text}  разово {day}".strip()
    if series.rule == ReminderRule.WEEKLY:
        days = ", ".join(WEEKDAY_LABELS[i] for i in series.weekdays)
        return f"{clock}  {text}  еженедельно {days}"
    if series.rule == ReminderRule.MONTHLY:
        day_n = series.month_day if series.month_day is not None else "?"
        return f"{clock}  {text}  ежемесячно, день {day_n}"
    return f"{clock}  {text}"


class ReminderNotifyDialog(QDialog):
    """Large non-modal popup. OK acknowledges; Open task also reveals; X leaves missed."""

    snooze_requested = Signal(int)
    open_task_requested = Signal()

    def __init__(
        self,
        title: str,
        body_html: str,
        parent=None,
        *,
        snooze_default_minutes: int = DEFAULT_SNOOZE_MINUTES,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Событие")
        self.setMinimumSize(560, 320)
        self.setWindowModality(Qt.WindowModality.NonModal)
        layout = QVBoxLayout(self)
        heading = QLabel(title)
        heading.setWordWrap(True)
        heading.setStyleSheet("font-weight: 600;")
        layout.addWidget(heading)
        self.body_edit = QTextBrowser()
        self.body_edit.setOpenLinks(False)
        self.body_edit.setOpenExternalLinks(False)
        self.body_edit.anchorClicked.connect(lambda url: _open_event_link(self, url))
        self.body_edit.setHtml(body_html or "—")
        layout.addWidget(self.body_edit, stretch=1)

        buttons = QHBoxLayout()
        self.snooze_combo = QComboBox()
        default = parse_snooze_minutes(snooze_default_minutes)
        for minutes in SNOOZE_MINUTES:
            self.snooze_combo.addItem(SNOOZE_LABELS[minutes], minutes)
        idx = self.snooze_combo.findData(default)
        self.snooze_combo.setCurrentIndex(idx if idx >= 0 else 3)
        snooze_btn = QPushButton("Напомнить через")
        snooze_btn.setObjectName("secondaryButton")
        snooze_btn.clicked.connect(self._snooze)
        buttons.addWidget(QLabel("Напомнить через"))
        buttons.addWidget(self.snooze_combo)
        buttons.addWidget(snooze_btn)
        buttons.addStretch()
        self.open_task_btn = QPushButton("Открыть заявку")
        self.open_task_btn.clicked.connect(self._open_task)
        buttons.addWidget(self.open_task_btn)
        ok = QPushButton("OK")
        ok.clicked.connect(self.accept)
        buttons.addWidget(ok)
        layout.addLayout(buttons)

    def _open_task(self) -> None:
        self.open_task_requested.emit()
        self.accept()

    def _snooze(self) -> None:
        minutes = int(self.snooze_combo.currentData())
        self.snooze_requested.emit(minutes)
        self.reject()


class ReminderCardDialog(QDialog):
    """Occurrence card: full text, moment, task; edit, open task, or delete the Event."""

    open_task_requested = Signal(int)
    series_deleted = Signal()
    event_changed = Signal()

    def __init__(
        self,
        service: TaskService,
        series: ReminderSeries,
        occ: datetime,
        task: Task | None,
        project_name: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Событие")
        self.setMinimumSize(480, 280)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self._service = service
        self._series = series
        self._task = task
        self._task_id = task.id if task is not None else None
        self._occ = occ
        self._project_name = project_name

        layout = QVBoxLayout(self)
        self.task_label = QLabel()
        self.task_label.setWordWrap(True)
        layout.addWidget(self.task_label)
        self.moment_label = QLabel()
        layout.addWidget(self.moment_label)
        self.body_label = QTextBrowser()
        self.body_label.setOpenLinks(False)
        self.body_label.setOpenExternalLinks(False)
        self.body_label.anchorClicked.connect(lambda url: _open_event_link(self, url))
        layout.addWidget(self.body_label, stretch=1)

        btns = QHBoxLayout()
        self.edit_btn = QPushButton("Изменить")
        self.open_task_btn = QPushButton("Открыть заявку")
        self.delete_event_btn = QPushButton("Удалить событие")
        self.delete_series_btn = self.delete_event_btn
        self.delete_event_btn.setObjectName("secondaryButton")
        self.edit_btn.clicked.connect(self._edit)
        self.open_task_btn.clicked.connect(self._open_task)
        self.delete_event_btn.clicked.connect(self._delete_event)
        btns.addWidget(self.edit_btn)
        btns.addWidget(self.open_task_btn)
        btns.addWidget(self.delete_event_btn)
        layout.addLayout(btns)
        self._refresh_view()

    def _sync_task_chrome(self) -> None:
        if self._task is not None:
            self.task_label.setText(f"{self._project_name} / №{self._task.number}")
            self.task_label.show()
            self.open_task_btn.show()
        else:
            self.task_label.clear()
            self.task_label.hide()
            self.open_task_btn.hide()

    def _refresh_view(self) -> None:
        repeating = " · повторяемое" if self._series.is_repeating else ""
        self.moment_label.setText(
            f"{self._occ.strftime('%d.%m.%Y %H:%M')}{repeating}"
        )
        self.body_label.setHtml(self._series.text or "—")
        self._sync_task_chrome()

    def _edit(self) -> None:
        dialog = ReminderEditDialog(
            self._service, self, task=self._task, series=self._series
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._series = dialog.save_to_service()
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self._reload_linked_task()
        self._refresh_view()
        self.event_changed.emit()

    def _reload_linked_task(self) -> None:
        if self._series.task_id is None:
            self._task = None
            self._task_id = None
            self._project_name = ""
            return
        try:
            self._task = self._service.get_task(self._series.task_id)
        except ServiceError:
            self._task = None
            self._task_id = None
            self._project_name = ""
            return
        self._task_id = self._task.id
        self._project_name = next(
            (p.name for p in self._service.list_projects() if p.id == self._task.project_id),
            "",
        )

    def _open_task(self) -> None:
        if self._task_id is not None:
            self.open_task_requested.emit(int(self._task_id))

    def _delete_event(self) -> None:
        if self._series.id is None:
            return
        answer = QMessageBox.question(self, "Удаление", "Удалить событие?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete_reminder(self._series.id)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.series_deleted.emit()
        self.accept()


class RemindersWindow(QDialog):
    open_task_requested = Signal(int)

    def __init__(self, service: TaskService, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Календарь")
        self.setMinimumSize(720, 520)
        self._service = service
        today = date.today()
        self._year = today.year
        self._month = today.month

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.calendar_page = QWidget()
        self.missed_page = QWidget()
        self.tabs.addTab(self.calendar_page, "Календарь")
        self.tabs.addTab(self.missed_page, "Пропущенные")
        layout.addWidget(self.tabs)

        self._build_calendar()
        self._build_missed()
        self.reload()

    def _build_calendar(self) -> None:
        layout = QVBoxLayout(self.calendar_page)
        nav = QHBoxLayout()
        prev_btn = QPushButton("◀")
        prev_btn.setObjectName("secondaryButton")
        prev_btn.clicked.connect(self._prev_month)
        next_btn = QPushButton("▶")
        next_btn.setObjectName("secondaryButton")
        next_btn.clicked.connect(self._next_month)
        self.month_label = QLabel()
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(prev_btn)
        nav.addWidget(self.month_label, stretch=1)
        nav.addWidget(next_btn)
        layout.addLayout(nav)

        self.day_grid = QWidget()
        self.day_layout = QVBoxLayout(self.day_grid)
        self.day_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.day_grid, stretch=1)

        add_btn = QPushButton("Создать событие…")
        add_btn.clicked.connect(lambda: self._create_reminder(initial_date=date.today()))
        layout.addWidget(add_btn)

    def _build_missed(self) -> None:
        layout = QVBoxLayout(self.missed_page)
        self.missed_list = QListWidget()
        layout.addWidget(self.missed_list)
        btns = QHBoxLayout()
        ack = QPushButton("Подтвердить")
        skip = QPushButton("Пропустить вхождение")
        delete = QPushButton("Удалить событие")
        open_task = QPushButton("Открыть заявку")
        ack.setObjectName("secondaryButton")
        skip.setObjectName("secondaryButton")
        delete.setObjectName("secondaryButton")
        open_task.setObjectName("secondaryButton")
        ack.clicked.connect(self._ack_selected)
        skip.clicked.connect(self._skip_selected)
        delete.clicked.connect(self._delete_selected)
        open_task.clicked.connect(self._open_selected_task)
        self.missed_list.itemClicked.connect(self._on_missed_clicked)
        btns.addWidget(ack)
        btns.addWidget(skip)
        btns.addWidget(delete)
        btns.addWidget(open_task)
        layout.addLayout(btns)

    def _prev_month(self) -> None:
        if self._month == 1:
            self._month = 12
            self._year -= 1
        else:
            self._month -= 1
        self.reload()

    def _next_month(self) -> None:
        if self._month == 12:
            self._month = 1
            self._year += 1
        else:
            self._month += 1
        self.reload()

    def reload(self) -> None:
        self.month_label.setText(f"{_MONTH_NAMES[self._month]} {self._year}")
        self._fill_calendar()
        self._fill_missed()

    def _month_occurrences(
        self,
    ) -> dict[date, list[tuple[ReminderSeries, datetime, Task | None]]]:
        first = date(self._year, self._month, 1)
        last_day = calendar.monthrange(self._year, self._month)[1]
        last = date(self._year, self._month, last_day)
        by_day: dict[date, list[tuple[ReminderSeries, datetime, Task | None]]] = {}
        for series in self._service.list_reminders():
            task: Task | None = None
            if series.task_id is not None:
                try:
                    task = self._service.get_task(series.task_id)
                except ServiceError:
                    continue
            for occ in occurrences_in_range(series, first, last):
                by_day.setdefault(occ.date(), []).append((series, occ, task))
        for items in by_day.values():
            items.sort(key=lambda row: row[1])
        return by_day

    def _fill_calendar(self) -> None:
        while self.day_layout.count():
            item = self.day_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        header = QHBoxLayout()
        for label in WEEKDAY_LABELS:
            cell = QLabel(label)
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.addWidget(cell)
        header_host = QWidget()
        header_host.setLayout(header)
        self.day_layout.addWidget(header_host)

        by_day = self._month_occurrences()
        cal = calendar.Calendar(firstweekday=0)
        for week in cal.monthdatescalendar(self._year, self._month):
            row = QHBoxLayout()
            for day in week:
                cell = QListWidget()
                cell.setMinimumHeight(88)
                in_month = day.month == self._month
                title = QListWidgetItem(str(day.day))
                title.setFlags(Qt.ItemFlag.NoItemFlags)
                if not in_month:
                    title.setForeground(Qt.GlobalColor.gray)
                cell.addItem(title)
                if in_month:
                    for series, occ, task in by_day.get(day, []):
                        plain = truncate_plain(html_to_plain(series.text) or "—")
                        clock = occ.strftime("%H:%M")
                        if task is not None:
                            line_text = f"{clock}  {plain}  №{task.number}"
                            task_id = task.id
                        else:
                            line_text = f"{clock}  {plain}"
                            task_id = None
                        line = QListWidgetItem(line_text)
                        line.setData(Qt.ItemDataRole.UserRole, (series.id, occ, task_id))
                        cell.addItem(line)
                    cell.itemClicked.connect(self._on_occurrence_clicked)
                    cell.itemDoubleClicked.connect(
                        lambda item, d=day: self._on_empty_day(item, d)
                    )
                row.addWidget(cell)
            host = QWidget()
            host.setLayout(row)
            self.day_layout.addWidget(host)

    def _on_occurrence_clicked(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if data is None:
            return
        series_id, occ, task_id = data
        self._open_reminder_card(
            int(series_id), occ, int(task_id) if task_id is not None else None
        )

    def _on_empty_day(self, item: QListWidgetItem, day: date) -> None:
        if item.data(Qt.ItemDataRole.UserRole) is None:
            self._create_reminder(initial_date=day)

    def _on_missed_clicked(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if data is None:
            return
        series_id, occ, task_id = data
        self._open_reminder_card(
            int(series_id), occ, int(task_id) if task_id is not None else None
        )

    def _open_reminder_card(
        self, series_id: int, occ: datetime, task_id: int | None
    ) -> None:
        try:
            series = self._service.get_reminder(series_id)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        task: Task | None = None
        project_name = ""
        if task_id is not None:
            try:
                task = self._service.get_task(task_id)
            except ServiceError as exc:
                QMessageBox.warning(self, "Ошибка", str(exc))
                return
            project_name = next(
                (p.name for p in self._service.list_projects() if p.id == task.project_id),
                "",
            )
        card = ReminderCardDialog(
            self._service, series, occ, task, project_name, self
        )
        card.open_task_requested.connect(self.open_task_requested.emit)
        card.series_deleted.connect(self.reload)
        card.event_changed.connect(self.reload)
        card.show()

    def _fill_missed(self) -> None:
        self.missed_list.clear()
        now = datetime.now()
        for series, occ, task, project in self._service.list_missed_reminders(now=now):
            repeating = " · повторяемое" if series.is_repeating else ""
            plain = html_to_plain(series.text) or "—"
            moment = occ.strftime("%d.%m.%Y %H:%M")
            if task is not None and project is not None:
                prefix = f"{project.name} / №{task.number}  "
                task_id = task.id
            else:
                prefix = ""
                task_id = None
            line = QListWidgetItem(f"{prefix}{moment}  {plain}{repeating}")
            line.setData(Qt.ItemDataRole.UserRole, (series.id, occ, task_id))
            self.missed_list.addItem(line)

    def _selected_missed(self) -> tuple[int, datetime, int | None] | None:
        item = self.missed_list.currentItem()
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        if data is None:
            return None
        series_id, occ, task_id = data
        return (
            int(series_id),
            occ,
            int(task_id) if task_id is not None else None,
        )

    def _ack_selected(self) -> None:
        selected = self._selected_missed()
        if selected is None:
            return
        series_id, occ, _task_id = selected
        try:
            self._service.acknowledge_reminder(series_id, occ)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.reload()

    def _skip_selected(self) -> None:
        selected = self._selected_missed()
        if selected is None:
            return
        series_id, occ, _task_id = selected
        try:
            self._service.skip_reminder_occurrence(series_id, occ)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.reload()

    def _delete_selected(self) -> None:
        selected = self._selected_missed()
        if selected is None:
            return
        series_id, _occ, _task_id = selected
        answer = QMessageBox.question(self, "Удаление", "Удалить событие?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete_reminder(series_id)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.reload()

    def _open_selected_task(self) -> None:
        selected = self._selected_missed()
        if selected is None or selected[2] is None:
            return
        self.open_task_requested.emit(selected[2])

    def _create_reminder(self, *, initial_date: date | None = None, task: Task | None = None) -> None:
        dialog = ReminderEditDialog(
            self._service,
            self,
            task=task,
            initial_date=initial_date,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            dialog.save_to_service()
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        self.reload()

    def create_for_task(self, task: Task) -> None:
        self._create_reminder(task=task, initial_date=date.today())
