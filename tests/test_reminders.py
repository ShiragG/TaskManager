from datetime import date, datetime, time
from pathlib import Path

import pytest

from taskmanager.domain import (
    ReminderRule,
    ReminderSeries,
    last_occurrence,
    missed_occurrence,
    occurrence_on,
    occurrences_in_range,
    skip_occurrence,
)
from taskmanager.infrastructure.filesystem import TaskFilesystem
from taskmanager.infrastructure.sqlite_repo import SqliteRepository
from taskmanager.services.settings_service import Settings
from taskmanager.services.task_service import (
    CreateTaskRequest,
    TaskService,
)


def _series(**kwargs) -> ReminderSeries:
    defaults = dict(
        id=1,
        task_id=1,
        text="пинг",
        time_of_day=time(9, 0),
        rule=ReminderRule.ONCE,
    )
    defaults.update(kwargs)
    return ReminderSeries(**defaults)


def test_once_occurrence_on_that_day_only():
    series = _series(once_date=date(2026, 8, 10))
    assert occurrence_on(series, date(2026, 8, 10)) == datetime(2026, 8, 10, 9, 0)
    assert occurrence_on(series, date(2026, 8, 11)) is None
    assert occurrences_in_range(series, date(2026, 8, 1), date(2026, 8, 31)) == [
        datetime(2026, 8, 10, 9, 0)
    ]


def test_weekly_monday_and_wednesday():
    series = _series(rule=ReminderRule.WEEKLY, weekdays=(0, 2))
    # 2026-08-10 is Monday, 12 is Wednesday, 11 is Tuesday
    assert occurrence_on(series, date(2026, 8, 10)) == datetime(2026, 8, 10, 9, 0)
    assert occurrence_on(series, date(2026, 8, 11)) is None
    assert occurrence_on(series, date(2026, 8, 12)) == datetime(2026, 8, 12, 9, 0)
    found = occurrences_in_range(series, date(2026, 8, 10), date(2026, 8, 16))
    assert found == [
        datetime(2026, 8, 10, 9, 0),
        datetime(2026, 8, 12, 9, 0),
    ]


def test_monthly_31st_skipped_in_february():
    series = _series(rule=ReminderRule.MONTHLY, month_day=31)
    assert occurrence_on(series, date(2026, 2, 28)) is None
    assert occurrences_in_range(series, date(2026, 2, 1), date(2026, 2, 28)) == []
    assert occurrence_on(series, date(2026, 1, 31)) == datetime(2026, 1, 31, 9, 0)
    assert occurrence_on(series, date(2026, 3, 31)) == datetime(2026, 3, 31, 9, 0)


def test_one_missed_per_series_is_the_latest():
    series = _series(rule=ReminderRule.WEEKLY, weekdays=(0,))
    now = datetime(2026, 8, 13, 12, 0)  # Thursday; last Monday is 10th
    missed = missed_occurrence(series, now)
    assert missed == datetime(2026, 8, 10, 9, 0)
    earlier = last_occurrence(series, datetime(2026, 8, 6, 12, 0))
    assert earlier == datetime(2026, 8, 3, 9, 0)
    # Still only the latest past fire is "missed"
    assert missed_occurrence(series, now) == datetime(2026, 8, 10, 9, 0)


def test_skip_occurrence_clears_missed():
    series = _series(rule=ReminderRule.WEEKLY, weekdays=(0,))
    now = datetime(2026, 8, 13, 12, 0)
    occ = missed_occurrence(series, now)
    assert occ is not None
    skip_occurrence(series, occ)
    assert missed_occurrence(series, now) is None


def test_acknowledge_clears_missed_but_occurrence_stays():
    from taskmanager.domain import acknowledge_series

    series = _series(once_date=date(2026, 8, 10))
    now = datetime(2026, 8, 10, 10, 0)
    occ = missed_occurrence(series, now)
    assert occ == datetime(2026, 8, 10, 9, 0)
    acknowledge_series(series, occ)
    assert missed_occurrence(series, now) is None
    assert occurrence_on(series, date(2026, 8, 10)) == datetime(2026, 8, 10, 9, 0)


@pytest.fixture
def service(tmp_path: Path):
    work = tmp_path / "work"
    work.mkdir()
    settings = Settings(work_dir=str(work))
    repo = SqliteRepository(tmp_path / "r.db")
    svc = TaskService(repo, settings, TaskFilesystem(settings))
    yield svc
    repo.close()


def test_archive_deletes_reminders_restore_does_not_revive(service: TaskService):
    project = service.create_project("Rem")
    task = service.create_task(
        CreateTaskRequest(project_id=project.id, number="1", create_folder=False)
    )
    series = service.create_reminder(
        task.id,
        text="пинг",
        time_of_day=time(9, 0),
        rule=ReminderRule.ONCE,
        once_date=date(2026, 8, 10),
    )
    assert service.list_reminders(task.id)
    service.archive_task(task.id)
    assert service.list_reminders(task.id) == []
    assert service.repo.get_reminder(series.id) is None
    service.restore_task(task.id)
    assert service.list_reminders(task.id) == []


def test_delete_task_cascades_reminders(service: TaskService):
    project = service.create_project("DelRem")
    task = service.create_task(
        CreateTaskRequest(project_id=project.id, number="1", create_folder=False)
    )
    series = service.create_reminder(
        task.id,
        text="пинг",
        time_of_day=time(9, 0),
        rule=ReminderRule.WEEKLY,
        weekdays=(0, 2),
    )
    service.delete_task(task.id, remove_folder=False)
    assert service.repo.get_reminder(series.id) is None


def test_hidden_does_not_delete_reminders(service: TaskService):
    from taskmanager.services.task_service import UpdateTaskRequest

    project = service.create_project("Hid")
    task = service.create_task(
        CreateTaskRequest(project_id=project.id, number="1", create_folder=False)
    )
    service.create_reminder(
        task.id,
        text="пинг",
        time_of_day=time(9, 0),
        rule=ReminderRule.ONCE,
        once_date=date(2026, 8, 10),
    )
    service.update_task(task.id, UpdateTaskRequest(hidden=True))
    assert len(service.list_reminders(task.id)) == 1


def test_create_event_without_task(service: TaskService):
    series = service.create_reminder(
        None,
        text="оплатить интернет",
        time_of_day=time(12, 0),
        rule=ReminderRule.ONCE,
        once_date=date(2026, 8, 13),
    )
    assert series.task_id is None
    loaded = service.get_reminder(series.id)
    assert loaded.task_id is None
    assert loaded.text == "оплатить интернет"


def test_bind_and_unbind_event_task(service: TaskService):
    project = service.create_project("Bind")
    task = service.create_task(
        CreateTaskRequest(project_id=project.id, number="1", create_folder=False)
    )
    series = service.create_reminder(
        None,
        text="созвон",
        time_of_day=time(10, 0),
        rule=ReminderRule.ONCE,
        once_date=date(2026, 8, 13),
    )
    bound = service.update_reminder(
        series.id,
        text="созвон",
        time_of_day=time(10, 0),
        rule=ReminderRule.ONCE,
        once_date=date(2026, 8, 13),
        task_id=task.id,
    )
    assert bound.task_id == task.id
    unbound = service.update_reminder(
        series.id,
        text="созвон",
        time_of_day=time(10, 0),
        rule=ReminderRule.ONCE,
        once_date=date(2026, 8, 13),
        task_id=None,
    )
    assert unbound.task_id is None


def test_archive_destroys_linked_event_standalone_remains(service: TaskService):
    project = service.create_project("Own")
    task = service.create_task(
        CreateTaskRequest(project_id=project.id, number="1", create_folder=False)
    )
    linked = service.create_reminder(
        task.id,
        text="на заявке",
        time_of_day=time(9, 0),
        rule=ReminderRule.ONCE,
        once_date=date(2026, 8, 10),
    )
    standalone = service.create_reminder(
        None,
        text="без заявки",
        time_of_day=time(9, 0),
        rule=ReminderRule.ONCE,
        once_date=date(2026, 8, 10),
    )
    service.archive_task(task.id)
    assert service.repo.get_reminder(linked.id) is None
    kept = service.get_reminder(standalone.id)
    assert kept.task_id is None
    assert kept.text == "без заявки"


def test_list_missed_includes_standalone_event(service: TaskService):
    from datetime import timedelta

    past = datetime.now().replace(second=0, microsecond=0) - timedelta(hours=1)
    series = service.create_reminder(
        None,
        text="пропущенное без заявки",
        time_of_day=past.time(),
        rule=ReminderRule.ONCE,
        once_date=past.date(),
    )
    missed = service.list_missed_reminders()
    assert len(missed) == 1
    found, when, task, project = missed[0]
    assert found.id == series.id
    assert task is None
    assert project is None
    assert when.date() == past.date()


@pytest.fixture
def reminder_ui(tmp_path: Path, qtbot):
    pytest.importorskip("PySide6")
    from taskmanager.ui.main_window import MainWindow
    from taskmanager.services.settings_service import SettingsStore

    work = tmp_path / "work"
    work.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    settings = Settings(work_dir=str(work))
    store.save(settings)
    repo = SqliteRepository(tmp_path / "rem-ui.db")
    svc = TaskService(repo, settings)
    window = MainWindow(svc, settings, store)
    qtbot.addWidget(window)
    yield window, svc, qtbot
    repo.close()


def test_reminder_create_filters_tasks_by_number_plain_and_project(reminder_ui):
    from PySide6.QtWidgets import QComboBox

    from taskmanager.ui.reminders_window import ReminderEditDialog

    window, service, qtbot = reminder_ui
    alpha = service.create_project("Alpha")
    beta = service.create_project("Beta")
    widget = service.create_task(
        CreateTaskRequest(
            project_id=alpha.id,
            number="42",
            description="visible widget",
            create_folder=False,
        )
    )
    service.create_task(
        CreateTaskRequest(
            project_id=beta.id,
            number="99",
            description="other gadget",
            create_folder=False,
        )
    )
    dialog = ReminderEditDialog(service, window, require_task_pick=True)
    qtbot.addWidget(dialog)

    assert not hasattr(dialog, "task_combo")
    combos = [
        w for w in dialog.findChildren(QComboBox) if w is not dialog.rule_combo
    ]
    assert combos == []
    assert dialog.task_list.count() == 2

    dialog.task_search.setText("42")
    assert dialog.task_list.count() == 1
    assert "42" in dialog.task_list.item(0).text()

    dialog.task_search.setText("widget")
    assert dialog.task_list.count() == 1
    dialog.task_list.setCurrentRow(0)
    assert "Alpha" in dialog.task_search.text()
    assert "42" in dialog.task_search.text()
    dialog.text_edit.html = "пинг"
    dialog._accept()
    assert dialog.task_id == widget.id

    dialog2 = ReminderEditDialog(service, window, require_task_pick=True)
    qtbot.addWidget(dialog2)
    dialog2.task_search.setText("beta")
    assert dialog2.task_list.count() == 1
    assert "99" in dialog2.task_list.item(0).text()


def test_reminder_notify_ok_acknowledges_close_does_not(reminder_ui, monkeypatch):
    from datetime import timedelta

    from taskmanager.domain import ReminderRule
    from taskmanager.ui.reminders_window import ReminderNotifyDialog

    window, service, qtbot = reminder_ui
    project = service.create_project("Ping")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id, number="7", create_folder=False
        )
    )
    occ = datetime.now().replace(second=0, microsecond=0) - timedelta(hours=1)
    series = service.create_reminder(
        task.id,
        text="полный текст пинга",
        time_of_day=occ.time(),
        rule=ReminderRule.ONCE,
        once_date=occ.date(),
    )
    assert service.list_missed_reminders()
    revealed: list[int] = []
    monkeypatch.setattr(window, "reveal_task", lambda tid: revealed.append(tid))

    window._notify_reminder(series, occ, task, project)
    popups = [
        w for w in window.findChildren(ReminderNotifyDialog) if w.isVisible()
    ]
    assert popups
    popup = popups[-1]
    assert popup.minimumWidth() >= 480
    assert popup.minimumHeight() >= 280
    popup.reject()
    assert service.list_missed_reminders()
    assert revealed == []

    window._notify_reminder(series, occ, task, project)
    popup = [
        w for w in window.findChildren(ReminderNotifyDialog) if w.isVisible()
    ][-1]
    popup.accept()
    assert service.list_missed_reminders() == []
    assert revealed == []


def test_reminder_notify_open_task_acknowledges_and_reveals(reminder_ui, monkeypatch):
    from datetime import timedelta

    from taskmanager.domain import ReminderRule
    from taskmanager.ui.reminders_window import ReminderNotifyDialog

    window, service, qtbot = reminder_ui
    project = service.create_project("OpenPing")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id, number="9", create_folder=False
        )
    )
    occ = datetime.now().replace(second=0, microsecond=0) - timedelta(hours=1)
    series = service.create_reminder(
        task.id,
        text="открыть заявку",
        time_of_day=occ.time(),
        rule=ReminderRule.ONCE,
        once_date=occ.date(),
    )
    revealed: list[int] = []
    monkeypatch.setattr(window, "reveal_task", lambda tid: revealed.append(tid))
    window._notify_reminder(series, occ, task, project)
    popup = [
        w for w in window.findChildren(ReminderNotifyDialog) if w.isVisible()
    ][-1]
    popup.open_task_btn.click()
    assert service.list_missed_reminders() == []
    assert revealed == [task.id]


def test_tray_reminder_click_acknowledges_and_opens_task(reminder_ui, monkeypatch):
    from datetime import timedelta

    from taskmanager.domain import ReminderRule

    window, service, qtbot = reminder_ui
    project = service.create_project("Tray")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id, number="8", create_folder=False
        )
    )
    occ = datetime.now().replace(second=0, microsecond=0) - timedelta(hours=1)
    series = service.create_reminder(
        task.id,
        text="tray ping",
        time_of_day=occ.time(),
        rule=ReminderRule.ONCE,
        once_date=occ.date(),
    )
    revealed: list[int] = []
    monkeypatch.setattr(window, "reveal_task", lambda tid: revealed.append(tid))
    window._pending_notify = (series.id, occ, task.id)
    window._on_tray_reminder_clicked()
    assert service.list_missed_reminders() == []
    assert revealed == [task.id]


def test_reminder_card_opens_task_and_deletes_series(reminder_ui, monkeypatch):
    from datetime import time as time_cls

    from PySide6.QtWidgets import QMessageBox

    from taskmanager.domain import ReminderRule
    from taskmanager.ui.reminders_window import ReminderCardDialog, RemindersWindow

    window, service, qtbot = reminder_ui
    project = service.create_project("Card")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id, number="11", create_folder=False
        )
    )
    occ_day = date.today()
    series = service.create_reminder(
        task.id,
        text="карточка пинга",
        time_of_day=time_cls(9, 30),
        rule=ReminderRule.ONCE,
        once_date=occ_day,
    )
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    opened: list[int] = []
    rem_win.open_task_requested.connect(opened.append)

    occ = datetime(occ_day.year, occ_day.month, occ_day.day, 9, 30)
    rem_win._open_reminder_card(series.id, occ, task.id)
    cards = rem_win.findChildren(ReminderCardDialog)
    assert cards
    card = cards[-1]
    assert "карточка пинга" in card.body_label.toPlainText()
    assert "11" in card.task_label.text()
    card.open_task_btn.click()
    assert opened == [task.id]

    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes
    )
    card.delete_event_btn.click()
    assert service.list_reminders(task.id) == []


def test_task_dialog_lists_reminder_series_and_can_delete(reminder_ui, monkeypatch):
    from datetime import time as time_cls

    from PySide6.QtWidgets import QMessageBox

    from taskmanager.domain import ReminderRule
    from taskmanager.ui.dialogs import TaskDialog
    from taskmanager.ui.reminders_window import format_reminder_series

    window, service, qtbot = reminder_ui
    project = service.create_project("Series")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id, number="12", create_folder=False
        )
    )
    series = service.create_reminder(
        task.id,
        text="серия на заявке",
        time_of_day=time_cls(8, 0),
        rule=ReminderRule.WEEKLY,
        weekdays=(0, 2),
    )
    rows = [
        (s.id, format_reminder_series(s))
        for s in service.list_reminders(task.id)
        if s.id is not None
    ]

    def on_delete(rid: int) -> bool:
        service.delete_reminder(rid)
        return True

    dialog = TaskDialog(
        window.settings,
        window,
        task=task,
        reminder_rows=rows,
        on_delete_reminder=on_delete,
    )
    qtbot.addWidget(dialog)
    assert not dialog.add_reminder_btn.isHidden()
    assert not dialog.delete_reminder_btn.isHidden()
    assert dialog.reminders_list.count() == 1
    assert "серия на заявке" in dialog.reminders_list.item(0).text()
    dialog.reminders_list.setCurrentRow(0)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes
    )
    dialog.delete_reminder_btn.click()
    assert dialog.reminders_list.count() == 0
    assert service.list_reminders(task.id) == []
    assert series.id is not None


def test_task_dialog_add_reminder_refreshes_list_without_closing(reminder_ui):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QDialog

    from taskmanager.ui.dialogs import TaskDialog
    from taskmanager.ui.reminders_window import ReminderEditDialog, format_reminder_series

    window, service, qtbot = reminder_ui
    project = service.create_project("AddFromTask")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id, number="15", create_folder=False
        )
    )
    service.create_reminder(
        task.id,
        text="уже есть",
        time_of_day=time(8, 0),
        rule=ReminderRule.ONCE,
        once_date=date.today(),
    )
    rows = [
        (s.id, format_reminder_series(s))
        for s in service.list_reminders(task.id)
        if s.id is not None
    ]

    dialog = TaskDialog(
        window.settings,
        window,
        task=task,
        reminder_rows=rows,
        reminder_service=service,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.isVisible()
    assert dialog.add_reminder_btn.isVisible()
    assert dialog.reminders_list.count() == 1

    def fill_and_accept() -> None:
        edits = dialog.findChildren(ReminderEditDialog)
        assert edits, "ReminderEditDialog did not open"
        edit = edits[0]
        assert edit.task_search.isVisible()
        assert edit.task_id == task.id
        edit.text_edit.html = "из диалога заявки"
        edit.accept()

    QTimer.singleShot(0, fill_and_accept)
    dialog.add_reminder_btn.click()

    assert dialog.isVisible()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.reminders_list.count() == 2
    assert "из диалога заявки" in dialog.reminders_list.item(1).text()
    texts = [series.text for series in service.list_reminders(task.id)]
    assert "из диалога заявки" in texts


def test_calendar_occurrence_click_opens_reminder_card_not_task(reminder_ui):
    from datetime import time as time_cls

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidget

    from taskmanager.domain import ReminderRule
    from taskmanager.ui.reminders_window import ReminderCardDialog, RemindersWindow

    window, service, qtbot = reminder_ui
    project = service.create_project("Cal")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id, number="13", create_folder=False
        )
    )
    today = date.today()
    service.create_reminder(
        task.id,
        text="календарный пинг",
        time_of_day=time_cls(10, 0),
        rule=ReminderRule.ONCE,
        once_date=today,
    )
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win._year = today.year
    rem_win._month = today.month
    rem_win.reload()
    opened: list[int] = []
    rem_win.open_task_requested.connect(opened.append)

    hit = None
    for cell in rem_win.findChildren(QListWidget):
        for i in range(cell.count()):
            item = cell.item(i)
            if item.data(Qt.ItemDataRole.UserRole):
                hit = (cell, item)
                break
        if hit:
            break
    assert hit is not None
    cell, item = hit
    cell.itemClicked.emit(item)
    cards = rem_win.findChildren(ReminderCardDialog)
    assert cards
    assert "календарный пинг" in cards[-1].body_label.toPlainText()
    assert opened == []


def test_calendar_window_title_and_no_series_word(reminder_ui):
    from PySide6.QtWidgets import QPushButton

    from taskmanager.ui.reminders_window import RemindersWindow

    window, service, qtbot = reminder_ui
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    assert rem_win.windowTitle() == "Календарь"
    assert window.act_reminders.text() == "Календарь"
    texts = [rem_win.windowTitle(), rem_win.tabs.tabText(0), rem_win.tabs.tabText(1)]
    texts.extend(btn.text() for btn in rem_win.findChildren(QPushButton))
    joined = " ".join(texts).casefold()
    assert "сери" not in joined


def test_event_form_monthly_day_comes_from_date(reminder_ui):
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QSpinBox

    from taskmanager.domain import ReminderRule
    from taskmanager.ui.reminders_window import ReminderEditDialog

    window, service, qtbot = reminder_ui
    dialog = ReminderEditDialog(service, window, require_task_pick=True)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.findChildren(QSpinBox) == []
    dialog.rule_combo.setCurrentIndex(
        dialog.rule_combo.findData(ReminderRule.MONTHLY.value)
    )
    assert dialog.once_date.isVisible()
    dialog.once_date.setDate(QDate(2026, 1, 31))
    assert dialog.month_day_value == 31
    dialog.rule_combo.setCurrentIndex(
        dialog.rule_combo.findData(ReminderRule.ONCE.value)
    )
    assert dialog.once_date.isVisible()
    dialog.rule_combo.setCurrentIndex(
        dialog.rule_combo.findData(ReminderRule.WEEKLY.value)
    )
    assert not dialog.once_date.isVisible()


def test_event_notify_snooze_does_not_acknowledge(reminder_ui, monkeypatch):
    from datetime import timedelta

    from taskmanager.domain import ReminderRule
    from taskmanager.ui.reminders_window import ReminderNotifyDialog

    window, service, qtbot = reminder_ui
    project = service.create_project("Snooze")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id, number="21", create_folder=False
        )
    )
    occ = datetime.now().replace(second=0, microsecond=0) - timedelta(hours=1)
    series = service.create_reminder(
        task.id,
        text="snooze ping",
        time_of_day=occ.time(),
        rule=ReminderRule.ONCE,
        once_date=occ.date(),
    )
    revealed: list[int] = []
    monkeypatch.setattr(window, "reveal_task", lambda tid: revealed.append(tid))
    window._notify_reminder(series, occ, task, project)
    popup = [
        w for w in window.findChildren(ReminderNotifyDialog) if w.isVisible()
    ][-1]
    assert popup.snooze_combo.currentData() == 15
    popup._snooze()
    assert service.list_missed_reminders()
    assert revealed == []
    key = (series.id, occ.isoformat(timespec="seconds"))
    assert key in window._snoozed_until


def test_task_dialog_double_click_edits_event(reminder_ui):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QDialog

    from taskmanager.domain import ReminderRule
    from taskmanager.ui.dialogs import TaskDialog
    from taskmanager.ui.reminders_window import ReminderEditDialog, format_reminder_series

    window, service, qtbot = reminder_ui
    project = service.create_project("EditFromTask")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id, number="22", create_folder=False
        )
    )
    series = service.create_reminder(
        task.id,
        text="старый текст",
        time_of_day=time(8, 0),
        rule=ReminderRule.ONCE,
        once_date=date.today(),
    )
    rows = [
        (s.id, format_reminder_series(s))
        for s in service.list_reminders(task.id)
        if s.id is not None
    ]
    dialog = TaskDialog(
        window.settings,
        window,
        task=task,
        reminder_rows=rows,
        reminder_service=service,
    )
    qtbot.addWidget(dialog)
    dialog.show()

    def fill_and_accept() -> None:
        edits = dialog.findChildren(ReminderEditDialog)
        assert edits, "ReminderEditDialog did not open"
        edit = edits[0]
        edit.text_edit.html = "новый текст"
        edit.accept()

    QTimer.singleShot(0, fill_and_accept)
    dialog.reminders_list.itemDoubleClicked.emit(dialog.reminders_list.item(0))
    assert dialog.isVisible()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "новый текст" in dialog.reminders_list.item(0).text()
    assert service.get_reminder(series.id).text == "новый текст"


def test_event_card_edit_updates_series(reminder_ui):
    from datetime import time as time_cls

    from PySide6.QtCore import QTimer

    from taskmanager.domain import ReminderRule
    from taskmanager.ui.reminders_window import (
        ReminderCardDialog,
        ReminderEditDialog,
        RemindersWindow,
    )

    window, service, qtbot = reminder_ui
    project = service.create_project("CardEdit")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id, number="23", create_folder=False
        )
    )
    occ_day = date.today()
    series = service.create_reminder(
        task.id,
        text="до правки",
        time_of_day=time_cls(9, 30),
        rule=ReminderRule.ONCE,
        once_date=occ_day,
    )
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    occ = datetime(occ_day.year, occ_day.month, occ_day.day, 9, 30)
    rem_win._open_reminder_card(series.id, occ, task.id)
    card = rem_win.findChildren(ReminderCardDialog)[-1]

    def fill_and_accept() -> None:
        edits = card.findChildren(ReminderEditDialog)
        assert edits
        edits[0].text_edit.html = "после правки"
        edits[0].accept()

    QTimer.singleShot(0, fill_and_accept)
    card.edit_btn.click()
    assert "после правки" in card.body_label.toPlainText()
    assert service.get_reminder(series.id).text == "после правки"


def test_event_form_ok_without_task_does_not_autoselect_only_task(reminder_ui):
    from taskmanager.ui.reminders_window import ReminderEditDialog

    window, service, qtbot = reminder_ui
    project = service.create_project("Only")
    service.create_task(
        CreateTaskRequest(
            project_id=project.id, number="1", create_folder=False
        )
    )
    dialog = ReminderEditDialog(service, window)
    qtbot.addWidget(dialog)
    assert dialog.task_list.count() == 1
    assert dialog.task_id is None
    dialog.text_edit.html = "без заявки"
    dialog._accept()
    assert dialog.result() == dialog.DialogCode.Accepted
    series = dialog.save_to_service()
    assert series.task_id is None
    assert service.get_reminder(series.id).task_id is None


def test_standalone_event_card_hides_open_task(reminder_ui):
    from datetime import time as time_cls

    from taskmanager.ui.reminders_window import ReminderCardDialog, RemindersWindow

    window, service, qtbot = reminder_ui
    series = service.create_reminder(
        None,
        text="карточка без заявки",
        time_of_day=time_cls(9, 30),
        rule=ReminderRule.ONCE,
        once_date=date.today(),
    )
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    today = date.today()
    occ = datetime(today.year, today.month, today.day, 9, 30)
    rem_win._open_reminder_card(series.id, occ, None)
    card = rem_win.findChildren(ReminderCardDialog)[-1]
    assert card.open_task_btn.isHidden()
    assert card.task_label.isHidden()
    assert "карточка без заявки" in card.body_label.toPlainText()


def test_notify_standalone_ok_and_toast_ack_without_reveal(reminder_ui, monkeypatch):
    from datetime import timedelta

    from taskmanager.ui.reminders_window import ReminderNotifyDialog

    window, service, qtbot = reminder_ui
    occ = datetime.now().replace(second=0, microsecond=0) - timedelta(hours=1)
    series = service.create_reminder(
        None,
        text="тост без заявки",
        time_of_day=occ.time(),
        rule=ReminderRule.ONCE,
        once_date=occ.date(),
    )
    revealed: list[int] = []
    monkeypatch.setattr(window, "reveal_task", lambda tid: revealed.append(tid))
    window._notify_reminder(series, occ, None, None)
    popup = [
        w for w in window.findChildren(ReminderNotifyDialog) if w.isVisible()
    ][-1]
    assert popup.open_task_btn.isHidden()
    popup.accept()
    assert service.list_missed_reminders() == []
    assert revealed == []

    later = occ.replace(minute=(occ.minute + 1) % 60)
    series2 = service.create_reminder(
        None,
        text="второй тост",
        time_of_day=later.time(),
        rule=ReminderRule.ONCE,
        once_date=later.date(),
    )
    window._pending_notify = (series2.id, later, None)
    window._on_tray_reminder_clicked()
    assert service.list_missed_reminders() == []
    assert revealed == []

