"""Calendar window and Event create/edit/notify dialogs."""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta

from PySide6.QtCore import QDate, QSize, QTime, QUrl, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QMouseEvent, QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
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
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QTimeEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from taskmanager.domain import (
    ReminderRule,
    ReminderSeries,
    Task,
    WEEKDAY_LABELS,
    html_to_plain,
    occurrence_on,
    occurrences_in_range,
    truncate_plain,
)
from taskmanager.infrastructure.platform_open import PlatformOpenError, open_target
from taskmanager.services.settings_service import (
    BASE_COLOR_NAMES,
    CALENDAR_VIEW_COMPACT,
    CALENDAR_VIEW_WEEK,
    DEFAULT_SNOOZE_MINUTES,
    SNOOZE_LABELS,
    SNOOZE_MINUTES,
    SettingsStore,
    parse_calendar_view,
    parse_snooze_minutes,
)
from taskmanager.services.task_service import ServiceError, TaskService
from taskmanager.ui.dialogs import ColorSwatchButton, HtmlEditRow, SWATCH_SIZE
from taskmanager.ui.event_sound_picker import EventSoundPicker

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

_MONTH_GENITIVE = (
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)

def _ru_days_word(n: int) -> str:
    n = abs(n)
    if n % 100 in (11, 12, 13, 14):
        return "дней"
    rem = n % 10
    if rem == 1:
        return "день"
    if rem in (2, 3, 4):
        return "дня"
    return "дней"


def _format_day_heading(day: date, *, today: date | None = None) -> str:
    today = date.today() if today is None else today
    base = (
        f"{WEEKDAY_LABELS[day.weekday()]}, {day.day} "
        f"{_MONTH_GENITIVE[day.month]} {day.year}"
    )
    delta = (day - today).days
    if delta == 0:
        return base
    word = _ru_days_word(delta)
    if delta < 0:
        return f"{base} · {abs(delta)} {word} назад"
    return f"{base} · через {delta} {word}"


def _event_color_icon(color: str) -> QIcon:
    pix = QPixmap(6, 16)
    pix.fill(QColor(color))
    return QIcon(pix)


def _apply_event_color(item: QListWidgetItem, color: str | None) -> None:
    if color:
        item.setIcon(_event_color_icon(color))
    else:
        item.setIcon(QIcon())


class CalendarDayCell(QListWidget):
    """One month-grid cell. Single click selects the day; rows do not open a card."""

    day_clicked = Signal(object)
    event_double_clicked = Signal(object)
    empty_double_clicked = Signal(object)

    def __init__(self, day: date, *, in_month: bool, parent=None) -> None:
        super().__init__(parent)
        self.day = day
        self.in_month = in_month
        self.setObjectName(f"dayCell_{day.isoformat()}")
        self.setMinimumHeight(36)
        self.setProperty("today", False)
        self.setProperty("selectedDay", False)
        self.setProperty("weekend", False)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        super().mousePressEvent(event)
        self.day_clicked.emit(self.day)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        item = self.itemAt(event.position().toPoint())
        super().mouseDoubleClickEvent(event)
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if data is not None:
            self.event_double_clicked.emit(data)
            return
        self.empty_double_clicked.emit(self.day)

    def apply_chrome(self, *, today: bool, selected: bool, weekend: bool = False) -> None:
        self.setProperty("today", today)
        self.setProperty("selectedDay", selected)
        self.setProperty("weekend", weekend)
        pal = self.palette()
        highlight = pal.color(QPalette.ColorRole.Highlight)
        fill = QColor(highlight)
        fill.setAlpha(46)
        mid = pal.color(QPalette.ColorRole.Mid)
        mid_fill = QColor(mid)
        mid_fill.setAlpha(40)
        window = pal.color(QPalette.ColorRole.Window)
        edge = (
            pal.color(QPalette.ColorRole.Dark)
            if window.lightness() >= 128
            else pal.color(QPalette.ColorRole.Mid)
        )
        if selected:
            border = highlight.name()
            border_w = 3
        else:
            border = edge.name()
            border_w = 2
        if today:
            bg = (
                f"rgba({fill.red()}, {fill.green()}, {fill.blue()}, {fill.alpha()})"
            )
        elif weekend:
            bg = (
                f"rgba({mid_fill.red()}, {mid_fill.green()}, {mid_fill.blue()}, "
                f"{mid_fill.alpha()})"
            )
        else:
            bg = "transparent"
        self.setStyleSheet(
            "QListWidget {"
            f" background-color: {bg};"
            f" border: {border_w}px solid {border};"
            " }"
        )


class DayEventsList(QListWidget):
    """Agenda list: double-click a row for the card; double-click empty space to create."""

    empty_double_clicked = Signal()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        item = self.itemAt(event.position().toPoint())
        super().mouseDoubleClickEvent(event)
        if item is None:
            self.empty_double_clicked.emit()


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

        self._event_color: str | None = series.color if series is not None else None
        self._color_swatches: list[ColorSwatchButton] = []
        self._color_host = QWidget()
        self._color_row = QHBoxLayout(self._color_host)
        self._color_row.setContentsMargins(0, 0, 0, 0)
        self._form.addRow("Цвет", self._color_host)
        self._rebuild_event_color_palette()

        self.sound_picker = EventSoundPicker(
            self,
            selected_path=series.sound_path if series is not None else None,
            include_settings_default=True,
            settings_path=service.settings.event_sound_path,
        )
        self.event_sound_combo = self.sound_picker.combo
        self.preview_sound_btn = self.sound_picker.preview_btn
        self._form.addRow("Звук", self.sound_picker)

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
        self._event_color = series.color
        self._sync_color_swatches()

    def _set_event_color(self, color: str | None) -> None:
        self._event_color = color
        self._sync_color_swatches()

    def _rebuild_event_color_palette(self) -> None:
        while self._color_row.count():
            item = self._color_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._color_swatches = []
        none_btn = QToolButton()
        none_btn.setText("∅")
        none_btn.setToolTip("Без цвета")
        none_btn.setFixedSize(SWATCH_SIZE, SWATCH_SIZE)
        none_btn.clicked.connect(lambda: self._set_event_color(None))
        self._color_none_btn = none_btn
        self._color_row.addWidget(none_btn)
        for name, hex_color in self._service.settings.colors.items():
            removable = name not in BASE_COLOR_NAMES
            btn = ColorSwatchButton(
                hex_color, tooltip=name, removable=removable
            )
            btn.setProperty("hexColor", hex_color)
            btn.clicked.connect(
                lambda _checked=False, c=hex_color: self._set_event_color(c)
            )
            if removable:
                btn.set_remove_handler(lambda n=name: self._remove_custom_color(n))
            self._color_swatches.append(btn)
            self._color_row.addWidget(btn)
        add_btn = QToolButton()
        add_btn.setText("+")
        add_btn.setToolTip("Добавить цвет")
        add_btn.setFixedSize(SWATCH_SIZE, SWATCH_SIZE)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setObjectName("secondaryButton")
        add_btn.clicked.connect(self._add_custom_color)
        self._color_row.addWidget(add_btn)
        self._color_row.addStretch()
        self._sync_color_swatches()

    def _find_settings_store(self) -> SettingsStore | None:
        widget = self.parent()
        while widget is not None:
            store = getattr(widget, "settings_store", None)
            if store is None:
                store = getattr(widget, "_settings_store", None)
            if isinstance(store, SettingsStore):
                return store
            widget = widget.parent()
        return None

    def _save_settings_colors(self) -> None:
        store = self._find_settings_store()
        if store is not None:
            store.save(self._service.settings)

    def _notify_task_palette(self) -> None:
        widget = self.parent()
        while widget is not None:
            rebuild = getattr(widget, "_rebuild_color_palette", None)
            if callable(rebuild):
                rebuild()
                return
            widget = widget.parent()

    def _add_custom_color(self) -> None:
        initial = QColor("#cccccc")
        color = QColorDialog.getColor(initial, self, "Выберите цвет")
        if not color.isValid():
            return
        hex_color = color.name()
        name = hex_color
        suffix = 2
        while name in self._service.settings.colors:
            name = f"{hex_color} ({suffix})"
            suffix += 1
        self._service.settings.colors[name] = hex_color
        self._save_settings_colors()
        self._rebuild_event_color_palette()
        self._notify_task_palette()
        self._set_event_color(hex_color)

    def _remove_custom_color(self, name: str) -> None:
        if name in BASE_COLOR_NAMES:
            return
        self._service.settings.colors.pop(name, None)
        self._save_settings_colors()
        self._rebuild_event_color_palette()
        self._notify_task_palette()

    def _sync_color_swatches(self) -> None:
        if getattr(self, "_color_none_btn", None) is None:
            return
        none_border = (
            "2px solid #0f766e"
            if self._event_color is None
            else "1px dashed #64748b"
        )
        self._color_none_btn.setStyleSheet(
            "QToolButton { background-color: #e2e8f0; "
            f"border: {none_border}; "
            "border-radius: 3px; color: #64748b; font-size: 11px; }"
        )
        for btn in self._color_swatches:
            hex_color = btn.hex_color
            selected = (
                self._event_color is not None
                and hex_color.lower() == self._event_color.lower()
            )
            border = (
                "#0f766e"
                if selected
                else (
                    "#94a3b8"
                    if hex_color.lower() in {"#ffffff", "#fff"}
                    else "#334155"
                )
            )
            width = "2px" if selected else "1px"
            btn.setStyleSheet(
                f"QToolButton {{ background-color: {hex_color}; "
                f"border: {width} solid {border}; border-radius: 3px; }}"
            )

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
            color=self._event_color,
            sound_path=self.sound_path,
        )
        if self._series_id is None:
            return self._service.create_reminder(self.task_id, **kwargs)
        return self._service.update_reminder(
            self._series_id, task_id=self.task_id, **kwargs
        )

    @property
    def sound_path(self) -> str | None:
        return self.sound_picker.current_path

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

    def __init__(
        self,
        service: TaskService,
        parent=None,
        *,
        settings_store: SettingsStore | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Календарь")
        self.setMinimumSize(880, 600)
        self.resize(1100, 720)
        self._service = service
        self._settings_store = settings_store or getattr(parent, "settings_store", None)
        today = date.today()
        self._year = today.year
        self._month = today.month
        self._selected_day: date | None = None
        self._cell_by_day: dict[date, CalendarDayCell] = {}

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.calendar_page = QWidget()
        self.missed_page = QWidget()
        self.tabs.addTab(self.calendar_page, "Календарь")
        self.tabs.addTab(self.missed_page, "Пропущенные")
        layout.addWidget(self.tabs)

        self._build_calendar()
        self._build_missed()
        self._restore_layout_on_show = True
        self.reload()

    def reject(self) -> None:
        self._save_calendar_layout()
        super().reject()

    def accept(self) -> None:
        self._save_calendar_layout()
        super().accept()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if not self._restore_layout_on_show:
            return
        self._restore_layout_on_show = False
        if self._service.settings.calendar_day_pane_open:
            self._open_day_pane(self._selected_day or date.today())

    def _build_calendar(self) -> None:
        layout = QVBoxLayout(self.calendar_page)
        self.calendar_splitter = QSplitter(Qt.Orientation.Vertical)
        self.calendar_splitter.setChildrenCollapsible(False)
        self.calendar_splitter.splitterMoved.connect(self._on_splitter_moved)

        self.day_pane = QWidget()
        self.day_pane.setObjectName("dayPane")
        pane_layout = QVBoxLayout(self.day_pane)
        pane_layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        self.day_pane_title = QLabel()
        self.day_pane_title.setObjectName("dayPaneTitle")
        self.day_pane_title.setStyleSheet("font-weight: 600;")
        self.close_day_pane_btn = QPushButton("×")
        self.close_day_pane_btn.setObjectName("secondaryButton")
        self.close_day_pane_btn.setFixedWidth(32)
        self.close_day_pane_btn.setToolTip("Закрыть")
        self.close_day_pane_btn.clicked.connect(self._collapse_day_pane)
        header.addWidget(self.day_pane_title, stretch=1)
        header.addWidget(self.close_day_pane_btn)
        pane_layout.addLayout(header)
        self.day_events = DayEventsList()
        self.day_events.setObjectName("dayEvents")
        self.day_events.itemDoubleClicked.connect(self._on_pane_item_double_clicked)
        self.day_events.empty_double_clicked.connect(self._on_pane_empty_double_click)
        pane_layout.addWidget(self.day_events, stretch=1)
        self.day_pane.hide()
        self.calendar_splitter.addWidget(self.day_pane)

        month_host = QWidget()
        month_layout = QVBoxLayout(month_host)
        month_layout.setContentsMargins(0, 0, 0, 0)
        nav = QHBoxLayout()
        prev_btn = QPushButton("◀")
        prev_btn.setObjectName("secondaryButton")
        prev_btn.clicked.connect(self._prev_period)
        next_btn = QPushButton("▶")
        next_btn.setObjectName("secondaryButton")
        next_btn.clicked.connect(self._next_period)
        self.month_label = QLabel()
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.calendar_view_combo = QComboBox()
        self.calendar_view_combo.setObjectName("calendarViewCombo")
        self.calendar_view_combo.addItem("Месяц", CALENDAR_VIEW_COMPACT)
        self.calendar_view_combo.addItem("Неделя", CALENDAR_VIEW_WEEK)
        view = parse_calendar_view(self._service.settings.calendar_view)
        idx = self.calendar_view_combo.findData(view)
        self.calendar_view_combo.blockSignals(True)
        self.calendar_view_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.calendar_view_combo.blockSignals(False)
        self.calendar_view_combo.currentIndexChanged.connect(
            self._on_calendar_view_changed
        )
        nav.addWidget(prev_btn)
        nav.addWidget(self.month_label, stretch=1)
        nav.addWidget(self.calendar_view_combo)
        nav.addWidget(next_btn)
        month_layout.addLayout(nav)

        self.day_grid = QWidget()
        self.day_layout = QVBoxLayout(self.day_grid)
        self.day_layout.setContentsMargins(0, 0, 0, 0)
        month_layout.addWidget(self.day_grid, stretch=1)
        self.calendar_splitter.addWidget(month_host)
        self.calendar_splitter.setStretchFactor(0, 3)
        self.calendar_splitter.setStretchFactor(1, 1)
        layout.addWidget(self.calendar_splitter, stretch=1)

        self.create_event_btn = QPushButton("Создать событие…")
        self.create_event_btn.clicked.connect(self._on_create_event_clicked)
        layout.addWidget(self.create_event_btn)

    def _build_missed(self) -> None:
        layout = QVBoxLayout(self.missed_page)
        self.missed_list = QListWidget()
        self.missed_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        layout.addWidget(self.missed_list)
        btns = QHBoxLayout()
        self.missed_select_all_btn = QPushButton("Выбрать все")
        self.missed_ack_btn = QPushButton("Подтвердить")
        self.missed_skip_btn = QPushButton("Пропустить вхождение")
        self.missed_delete_btn = QPushButton("Удалить событие")
        self.missed_open_task_btn = QPushButton("Открыть заявку")
        self.missed_ack_all_btn = QPushButton("Подтвердить всё")
        self.missed_delete_all_btn = QPushButton("Удалить всё")
        for btn in (
            self.missed_select_all_btn,
            self.missed_ack_btn,
            self.missed_skip_btn,
            self.missed_delete_btn,
            self.missed_open_task_btn,
            self.missed_ack_all_btn,
            self.missed_delete_all_btn,
        ):
            btn.setObjectName("secondaryButton")
        self.missed_select_all_btn.clicked.connect(self._select_all_missed)
        self.missed_ack_btn.clicked.connect(self._ack_selected)
        self.missed_skip_btn.clicked.connect(self._skip_selected)
        self.missed_delete_btn.clicked.connect(self._delete_selected)
        self.missed_open_task_btn.clicked.connect(self._open_selected_task)
        self.missed_ack_all_btn.clicked.connect(self._ack_all_missed)
        self.missed_delete_all_btn.clicked.connect(self._delete_all_missed)
        self.missed_list.itemDoubleClicked.connect(self._on_missed_clicked)
        self.missed_list.itemSelectionChanged.connect(self._sync_missed_actions)
        btns.addWidget(self.missed_select_all_btn)
        btns.addWidget(self.missed_ack_btn)
        btns.addWidget(self.missed_skip_btn)
        btns.addWidget(self.missed_delete_btn)
        btns.addWidget(self.missed_open_task_btn)
        btns.addWidget(self.missed_ack_all_btn)
        btns.addWidget(self.missed_delete_all_btn)
        layout.addLayout(btns)

    def _calendar_view(self) -> str:
        return parse_calendar_view(self._service.settings.calendar_view)

    def _grid_shows_week(self) -> bool:
        return self._calendar_view() == CALENDAR_VIEW_WEEK

    def _grid_is_compact_month(self) -> bool:
        return self._calendar_view() == CALENDAR_VIEW_COMPACT

    def _persist_settings(self) -> None:
        if self._settings_store is not None:
            self._settings_store.save(self._service.settings)

    def _on_calendar_view_changed(self) -> None:
        view = self.calendar_view_combo.currentData()
        self._service.settings.calendar_view = parse_calendar_view(view)
        self._persist_settings()
        self._fill_calendar()
        if self.day_pane.isVisible() and self._selected_day is not None:
            self._fill_day_pane(self._selected_day)
            self._apply_open_pane_splitter()

    def _prev_period(self) -> None:
        if self._grid_shows_week():
            self._shift_week(-1)
            return
        self._prev_month()

    def _next_period(self) -> None:
        if self._grid_shows_week():
            self._shift_week(1)
            return
        self._next_month()

    def _shift_week(self, weeks: int) -> None:
        day = self._selected_day or date.today()
        self._selected_day = day + timedelta(weeks=weeks)
        self._year = self._selected_day.year
        self._month = self._selected_day.month
        self.reload()

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
        if self.day_pane.isVisible() and self._selected_day is not None:
            self._fill_day_pane(self._selected_day)

    def _occurrences_in_span(
        self, first: date, last: date
    ) -> dict[date, list[tuple[ReminderSeries, datetime, Task | None]]]:
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

    def _occurrences_on(
        self, day: date
    ) -> list[tuple[ReminderSeries, datetime, Task | None]]:
        rows: list[tuple[ReminderSeries, datetime, Task | None]] = []
        for series in self._service.list_reminders():
            task: Task | None = None
            if series.task_id is not None:
                try:
                    task = self._service.get_task(series.task_id)
                except ServiceError:
                    continue
            occ = occurrence_on(series, day)
            if occ is not None:
                rows.append((series, occ, task))
        rows.sort(key=lambda row: row[1])
        return rows

    def _weeks_to_show(self) -> list[list[date]]:
        cal = calendar.Calendar(firstweekday=0)
        if self._grid_shows_week():
            day = self._selected_day or date.today()
            for week in cal.monthdatescalendar(day.year, day.month):
                if day in week:
                    return [week]
            monday = day - timedelta(days=day.weekday())
            return [[monday + timedelta(days=i) for i in range(7)]]
        return cal.monthdatescalendar(self._year, self._month)

    def _clear_day_grid(self) -> None:
        while self.day_layout.count():
            item = self.day_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self._cell_by_day = {}

    def _fill_calendar(self) -> None:
        self._clear_day_grid()

        header = QHBoxLayout()
        for label in WEEKDAY_LABELS:
            cell = QLabel(label)
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.addWidget(cell)
        header_host = QWidget()
        header_host.setLayout(header)
        self.day_layout.addWidget(header_host)

        weeks = self._weeks_to_show()
        first = min(weeks[0][0], weeks[-1][0])
        last = max(weeks[0][-1], weeks[-1][-1])
        by_day = self._occurrences_in_span(first, last)
        today = date.today()
        compact = self._grid_is_compact_month()
        week_mode = self._grid_shows_week()
        for week in weeks:
            row = QHBoxLayout()
            for day in week:
                in_month = day.month == self._month
                cell = CalendarDayCell(day, in_month=in_month)
                title = QListWidgetItem(str(day.day))
                title.setFlags(Qt.ItemFlag.ItemIsEnabled)
                if not in_month and not week_mode:
                    title.setForeground(Qt.GlobalColor.gray)
                cell.addItem(title)
                events = by_day.get(day, [])
                show_events = in_month or week_mode
                if show_events and compact:
                    self._add_event_dots(cell, events)
                elif show_events:
                    for series, occ, task in events:
                        cell.addItem(self._occurrence_item(series, occ, task))
                cell.day_clicked.connect(self._on_day_clicked)
                cell.event_double_clicked.connect(self._on_cell_event_double_clicked)
                cell.empty_double_clicked.connect(self._on_cell_empty_double_clicked)
                cell.apply_chrome(
                    today=day == today,
                    selected=self._selected_day == day
                    and (week_mode or self.day_pane.isVisible()),
                    weekend=day.weekday() in (5, 6),
                )
                self._cell_by_day[day] = cell
                row.addWidget(cell)
            host = QWidget()
            host.setLayout(row)
            self.day_layout.addWidget(host, stretch=1 if week_mode else 0)

    def _add_event_dots(
        self,
        cell: CalendarDayCell,
        events: list[tuple[ReminderSeries, datetime, Task | None]],
    ) -> None:
        if not events:
            return
        item = QListWidgetItem()
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        item.setSizeHint(QSize(1, 12))
        cell.addItem(item)
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(2, 0, 2, 0)
        row.setSpacing(2)
        for series, _occ, _task in events:
            color = series.color or "#64748b"
            dot = QLabel()
            dot.setFixedSize(8, 8)
            dot.setStyleSheet(
                f"background-color: {color}; border-radius: 4px;"
            )
            row.addWidget(dot)
        row.addStretch()
        cell.setItemWidget(item, host)

    def _occurrence_item(
        self,
        series: ReminderSeries,
        occ: datetime,
        task: Task | None,
    ) -> QListWidgetItem:
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
        _apply_event_color(line, series.color)
        return line

    def _on_day_clicked(self, day: object) -> None:
        if not isinstance(day, date):
            return
        if (
            not self._grid_shows_week()
            and self._selected_day == day
            and self.day_pane.isVisible()
        ):
            self._collapse_day_pane()
            return
        self._open_day_pane(day)

    def _on_cell_event_double_clicked(self, data: object) -> None:
        if not self._grid_shows_week() or data is None:
            return
        series_id, occ, task_id = data
        self._open_reminder_card(
            int(series_id), occ, int(task_id) if task_id is not None else None
        )

    def _on_cell_empty_double_clicked(self, day: object) -> None:
        if not self._grid_shows_week() or not isinstance(day, date):
            return
        self._selected_day = day
        self._year = day.year
        self._month = day.month
        self._create_reminder(initial_date=day)

    def _open_day_pane(self, day: date) -> None:
        was_hidden = self.day_pane.isHidden()
        self._selected_day = day
        self._year = day.year
        self._month = day.month
        self.day_pane.setMinimumHeight(160)
        self.day_pane.show()
        if was_hidden:
            self._apply_open_pane_splitter()
            self._service.settings.calendar_day_pane_open = True
            self._persist_settings()
        self._fill_calendar()
        self._fill_day_pane(day)

    def _saved_splitter_sizes(self) -> list[int]:
        settings = self._service.settings
        if self._grid_shows_week():
            return list(settings.calendar_week_splitter)
        return list(settings.calendar_compact_splitter)

    def _store_splitter_sizes(self, sizes: list[int]) -> None:
        if self._grid_shows_week():
            self._service.settings.calendar_week_splitter = list(sizes)
        else:
            self._service.settings.calendar_compact_splitter = list(sizes)

    def _on_splitter_moved(self, _pos: int = 0, _index: int = 0) -> None:
        if not self.day_pane.isVisible():
            return
        sizes = [int(value) for value in self.calendar_splitter.sizes()]
        if len(sizes) != 2 or sizes[0] < 1 or sizes[1] < 1:
            return
        self._store_splitter_sizes(sizes)
        self._persist_settings()

    def _save_calendar_layout(self) -> None:
        settings = self._service.settings
        settings.calendar_view = self._calendar_view()
        settings.calendar_day_pane_open = self.day_pane.isVisible()
        if self.day_pane.isVisible():
            sizes = [int(value) for value in self.calendar_splitter.sizes()]
            if len(sizes) == 2 and sizes[0] > 0 and sizes[1] > 0:
                self._store_splitter_sizes(sizes)
        self._persist_settings()

    def _apply_open_pane_splitter(self) -> None:
        total = self.calendar_splitter.size().height()
        if total < 200:
            total = 560
        saved = self._saved_splitter_sizes()
        if len(saved) == 2 and saved[0] + saved[1] > 0:
            weight = saved[0] + saved[1]
            pane_h = max(total * saved[0] // weight, 160)
            grid_h = max(total - pane_h, 80)
        elif self._grid_shows_week():
            pane_h = max(total // 2, 160)
            grid_h = max(total - pane_h, 80)
        else:
            pane_h = max(total * 3 // 4, 160)
            grid_h = max(total - pane_h, 80)
        self.calendar_splitter.blockSignals(True)
        self.calendar_splitter.setSizes([pane_h, grid_h])
        self.calendar_splitter.setStretchFactor(0, max(pane_h, 1))
        self.calendar_splitter.setStretchFactor(1, max(grid_h, 1))
        self.calendar_splitter.blockSignals(False)
        applied = [int(value) for value in self.calendar_splitter.sizes()]
        if len(applied) == 2 and applied[0] > 0 and applied[1] > 0:
            self._store_splitter_sizes(applied)
        else:
            self._store_splitter_sizes([pane_h, grid_h])

    def _collapse_day_pane(self) -> None:
        if self.day_pane.isVisible():
            sizes = [int(value) for value in self.calendar_splitter.sizes()]
            if len(sizes) == 2 and sizes[0] > 0 and sizes[1] > 0:
                self._store_splitter_sizes(sizes)
        self.day_pane.hide()
        self.day_pane.setMinimumHeight(0)
        self._fill_calendar()
        self._service.settings.calendar_day_pane_open = False
        self._persist_settings()

    def _fill_day_pane(self, day: date) -> None:
        self.day_pane_title.setText(_format_day_heading(day))
        self.day_events.clear()
        for series, occ, task in self._occurrences_on(day):
            self.day_events.addItem(self._occurrence_item(series, occ, task))

    def _on_pane_item_double_clicked(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if data is None:
            return
        series_id, occ, task_id = data
        self._open_reminder_card(
            int(series_id), occ, int(task_id) if task_id is not None else None
        )

    def _on_pane_empty_double_click(self) -> None:
        self._create_reminder(initial_date=self._event_create_date())

    def _on_create_event_clicked(self) -> None:
        self._create_reminder(initial_date=self._event_create_date())

    def _event_create_date(self) -> date:
        if self._selected_day is not None and (
            self.day_pane.isVisible() or self._grid_shows_week()
        ):
            return self._selected_day
        return date.today()

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
        self._sync_missed_actions()

    def _missed_item_data(
        self, item: QListWidgetItem | None
    ) -> tuple[int, datetime, int | None] | None:
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

    def _missed_rows_from_items(
        self, items: list[QListWidgetItem]
    ) -> list[tuple[int, datetime, int | None]]:
        rows: list[tuple[int, datetime, int | None]] = []
        for item in items:
            parsed = self._missed_item_data(item)
            if parsed is not None:
                rows.append(parsed)
        return rows

    def _selected_missed_rows(self) -> list[tuple[int, datetime, int | None]]:
        return self._missed_rows_from_items(self.missed_list.selectedItems())

    def _all_missed_rows(self) -> list[tuple[int, datetime, int | None]]:
        items = [
            item
            for i in range(self.missed_list.count())
            if (item := self.missed_list.item(i)) is not None
        ]
        return self._missed_rows_from_items(items)

    def _sync_missed_actions(self) -> None:
        selected = self._selected_missed_rows()
        n_sel = len(selected)
        n_all = self.missed_list.count()
        has_sel = n_sel > 0
        self.missed_ack_btn.setEnabled(has_sel)
        self.missed_skip_btn.setEnabled(has_sel)
        self.missed_delete_btn.setEnabled(has_sel)
        self.missed_open_task_btn.setEnabled(
            n_sel == 1 and selected[0][2] is not None
        )
        self.missed_select_all_btn.setEnabled(n_all > 0)
        self.missed_ack_all_btn.setEnabled(n_all > 0)
        self.missed_delete_all_btn.setEnabled(n_all > 0)

    def _select_all_missed(self) -> None:
        self.missed_list.selectAll()

    def _ack_rows(
        self, rows: list[tuple[int, datetime, int | None]]
    ) -> None:
        if not rows:
            return
        try:
            for series_id, occ, _task_id in rows:
                self._service.acknowledge_reminder(series_id, occ)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
        self.reload()

    def _skip_rows(
        self, rows: list[tuple[int, datetime, int | None]]
    ) -> None:
        if not rows:
            return
        try:
            for series_id, occ, _task_id in rows:
                self._service.skip_reminder_occurrence(series_id, occ)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
        self.reload()

    def _delete_events_prompt(self, count: int) -> bool:
        if count <= 0:
            return False
        text = "Удалить событие?" if count == 1 else f"Удалить {count} событий?"
        answer = QMessageBox.question(self, "Удаление", text)
        return answer == QMessageBox.StandardButton.Yes

    def _delete_rows(
        self, rows: list[tuple[int, datetime, int | None]]
    ) -> None:
        if not rows:
            return
        series_ids: list[int] = []
        seen: set[int] = set()
        for series_id, _occ, _task_id in rows:
            if series_id in seen:
                continue
            seen.add(series_id)
            series_ids.append(series_id)
        if not self._delete_events_prompt(len(series_ids)):
            return
        try:
            for series_id in series_ids:
                self._service.delete_reminder(series_id)
        except ServiceError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
        self.reload()

    def _ack_selected(self) -> None:
        self._ack_rows(self._selected_missed_rows())

    def _skip_selected(self) -> None:
        self._skip_rows(self._selected_missed_rows())

    def _delete_selected(self) -> None:
        self._delete_rows(self._selected_missed_rows())

    def _ack_all_missed(self) -> None:
        self._ack_rows(self._all_missed_rows())

    def _delete_all_missed(self) -> None:
        self._delete_rows(self._all_missed_rows())

    def _open_selected_task(self) -> None:
        selected = self._selected_missed_rows()
        if len(selected) != 1 or selected[0][2] is None:
            return
        self.open_task_requested.emit(selected[0][2])

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
