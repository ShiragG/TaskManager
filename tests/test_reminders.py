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
        w
        for w in dialog.findChildren(QComboBox)
        if w is not dialog.rule_combo and w is not dialog.event_sound_combo
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


def test_calendar_occurrence_click_opens_day_pane_not_card(reminder_ui):
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
    rem_win.show()
    rem_win._year = today.year
    rem_win._month = today.month
    rem_win.reload()
    opened: list[int] = []
    rem_win.open_task_requested.connect(opened.append)

    cell = rem_win.findChild(QListWidget, f"dayCell_{today.isoformat()}")
    assert cell is not None
    qtbot.mouseClick(cell.viewport(), Qt.MouseButton.LeftButton)
    cards = [c for c in rem_win.findChildren(ReminderCardDialog) if c.isVisible()]
    assert cards == []
    assert rem_win.day_pane.isVisible()
    assert opened == []
    assert "календарный пинг" in rem_win.day_events.item(0).text()


def test_calendar_window_title_and_no_series_word(reminder_ui):
    from PySide6.QtWidgets import QPushButton

    from taskmanager.ui.reminders_window import RemindersWindow

    window, service, qtbot = reminder_ui
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    assert rem_win.windowTitle() == "Календарь"
    assert rem_win.width() >= 1100
    assert rem_win.height() >= 720
    assert rem_win.minimumWidth() > 720
    assert rem_win.minimumHeight() > 520
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


def test_event_color_roundtrip(service: TaskService):
    series = service.create_reminder(
        None,
        text="цветное",
        time_of_day=time(11, 0),
        rule=ReminderRule.ONCE,
        once_date=date(2026, 8, 18),
        color="#ff0000",
    )
    loaded = service.get_reminder(series.id)
    assert loaded.color == "#ff0000"
    cleared = service.update_reminder(
        series.id,
        text="цветное",
        time_of_day=time(11, 0),
        rule=ReminderRule.ONCE,
        once_date=date(2026, 8, 18),
        color=None,
    )
    assert cleared.color is None


def test_event_sound_path_roundtrip(service: TaskService):
    series = service.create_reminder(
        None,
        text="со своим звуком",
        time_of_day=time(11, 0),
        rule=ReminderRule.ONCE,
        once_date=date(2026, 8, 18),
        sound_path="/tmp/own.wav",
    )
    loaded = service.get_reminder(series.id)
    assert loaded.sound_path == "/tmp/own.wav"
    defaulted = service.update_reminder(
        series.id,
        text="со своим звуком",
        time_of_day=time(11, 0),
        rule=ReminderRule.ONCE,
        once_date=date(2026, 8, 18),
        sound_path=None,
    )
    assert defaulted.sound_path is None


def test_event_form_sound_combo_defaults_to_settings(reminder_ui):
    from taskmanager.infrastructure.event_sounds import SETTINGS_SOUND_SENTINEL
    from taskmanager.ui.reminders_window import ReminderEditDialog

    window, service, qtbot = reminder_ui
    dialog = ReminderEditDialog(service, window)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.event_sound_combo.itemText(0) == "Как в настройках"
    assert dialog.event_sound_combo.currentData() == SETTINGS_SOUND_SENTINEL
    assert dialog.preview_sound_btn.text() == "Прослушать"
    assert dialog.sound_path is None


def test_notify_plays_event_sound_or_settings_or_silence(reminder_ui, monkeypatch):
    from datetime import timedelta

    from taskmanager.domain import ReminderRule

    window, service, qtbot = reminder_ui
    occ = datetime.now().replace(second=0, microsecond=0) - timedelta(hours=1)
    series = service.create_reminder(
        None,
        text="звук",
        time_of_day=occ.time(),
        rule=ReminderRule.ONCE,
        once_date=occ.date(),
    )
    played: list[str] = []
    monkeypatch.setattr(
        window._event_sound_player, "play", lambda path: played.append(path) or True
    )
    window.settings.event_sound_enabled = True
    window.settings.event_sound_path = "/settings/ding.wav"
    window._notify_reminder(series, occ, None, None)
    assert played[-1] == "/settings/ding.wav"

    own = service.update_reminder(
        series.id,
        text="звук",
        time_of_day=occ.time(),
        rule=ReminderRule.ONCE,
        once_date=occ.date(),
        sound_path="/event/own.wav",
    )
    window._notify_reminder(own, occ, None, None)
    assert played[-1] == "/event/own.wav"

    window.settings.event_sound_enabled = False
    before = list(played)
    window._notify_reminder(own, occ, None, None)
    assert played == before


def test_calendar_today_fill_and_toggle_day_pane(reminder_ui):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidget

    from taskmanager.ui.reminders_window import RemindersWindow

    window, service, qtbot = reminder_ui
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    today = date.today()
    cell = rem_win.findChild(QListWidget, f"dayCell_{today.isoformat()}")
    assert cell is not None
    assert cell.property("today") is True
    assert rem_win.day_pane.isHidden()

    qtbot.mouseClick(cell.viewport(), Qt.MouseButton.LeftButton)
    assert rem_win.day_pane.isVisible()
    cell = rem_win.findChild(QListWidget, f"dayCell_{today.isoformat()}")
    assert cell is not None
    assert cell.property("selectedDay") is True
    heading = rem_win.day_pane_title.text()
    assert str(today.day) in heading
    assert str(today.year) in heading
    assert "назад" not in heading
    assert "через" not in heading

    qtbot.mouseClick(cell.viewport(), Qt.MouseButton.LeftButton)
    assert rem_win.day_pane.isHidden()
    cell = rem_win.findChild(QListWidget, f"dayCell_{today.isoformat()}")
    assert cell is not None
    assert cell.property("selectedDay") is False


def test_calendar_pane_click_opens_card_and_create_uses_selected_day(reminder_ui):
    from datetime import time as time_cls

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QListWidget

    from taskmanager.ui.reminders_window import (
        ReminderCardDialog,
        ReminderEditDialog,
        RemindersWindow,
    )

    window, service, qtbot = reminder_ui
    today = date.today()
    last = date(today.year, today.month, 28) if today.day != 28 else date(
        today.year, today.month, 27
    )
    service.create_reminder(
        None,
        text="в панели",
        time_of_day=time_cls(9, 0),
        rule=ReminderRule.ONCE,
        once_date=last,
    )
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    cell = rem_win.findChild(QListWidget, f"dayCell_{last.isoformat()}")
    assert cell is not None
    qtbot.mouseClick(cell.viewport(), Qt.MouseButton.LeftButton)
    assert rem_win.day_pane.isVisible()
    assert rem_win.day_events.count() == 1
    rem_win.day_events.itemClicked.emit(rem_win.day_events.item(0))
    cards = [c for c in rem_win.findChildren(ReminderCardDialog) if c.isVisible()]
    assert cards == []
    rem_win.day_events.itemDoubleClicked.emit(rem_win.day_events.item(0))
    cards = [c for c in rem_win.findChildren(ReminderCardDialog) if c.isVisible()]
    assert cards
    assert "в панели" in cards[-1].body_label.toPlainText()

    captured: list[date] = []

    def grab_and_reject() -> None:
        edits = rem_win.findChildren(ReminderEditDialog)
        assert edits
        captured.append(edits[0].once_date_value)
        edits[0].reject()

    QTimer.singleShot(0, grab_and_reject)
    rem_win.create_event_btn.click()
    assert captured == [last]


def test_calendar_event_color_stripe(reminder_ui):
    from datetime import time as time_cls

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel, QListWidget

    from taskmanager.ui.reminders_window import RemindersWindow

    window, service, qtbot = reminder_ui
    today = date.today()
    service.create_reminder(
        None,
        text="полоска",
        time_of_day=time_cls(12, 0),
        rule=ReminderRule.ONCE,
        once_date=today,
        color="#ff0000",
    )
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.reload()
    cell = rem_win.findChild(QListWidget, f"dayCell_{today.isoformat()}")
    assert cell is not None
    dotted = False

    for i in range(cell.count()):
        host = cell.itemWidget(cell.item(i))
        if host is None:
            continue
        for label in host.findChildren(QLabel):
            if "#ff0000" in label.styleSheet():
                dotted = True
    assert dotted
    qtbot.mouseClick(cell.viewport(), Qt.MouseButton.LeftButton)
    pane_item = rem_win.day_events.item(0)
    assert pane_item is not None
    assert not pane_item.icon().isNull()


def test_opening_pane_compacts_grid_and_splitter_stays_open(reminder_ui):
    from datetime import time as time_cls

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidget

    from taskmanager.ui.reminders_window import CalendarDayCell, RemindersWindow

    window, service, qtbot = reminder_ui
    today = date.today()
    service.create_reminder(
        None,
        text="точка в сетке",
        time_of_day=time_cls(10, 0),
        rule=ReminderRule.ONCE,
        once_date=today,
    )
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    rem_win.resize(1100, 720)
    assert rem_win.day_pane.isHidden()
    cell = rem_win.findChild(QListWidget, f"dayCell_{today.isoformat()}")
    assert cell is not None
    has_dots = False
    for i in range(cell.count()):
        item = cell.item(i)
        assert item.data(Qt.ItemDataRole.UserRole) is None
        assert "точка в сетке" not in item.text()
        if cell.itemWidget(item) is not None:
            has_dots = True
    assert has_dots
    qtbot.mouseClick(cell.viewport(), Qt.MouseButton.LeftButton)
    assert rem_win.day_pane.isVisible()
    assert rem_win.calendar_splitter.childrenCollapsible() is False
    sizes = rem_win.calendar_splitter.sizes()
    assert sizes[0] > 0
    assert sizes[1] > 0
    cell = rem_win.findChild(QListWidget, f"dayCell_{today.isoformat()}")
    assert cell is not None
    assert cell.minimumHeight() <= 36
    for i in range(cell.count()):
        item = cell.item(i)
        assert item.data(Qt.ItemDataRole.UserRole) is None
        assert "точка в сетке" not in item.text()
    assert rem_win.day_events.count() == 1
    assert "точка в сетке" in rem_win.day_events.item(0).text()
    assert len(rem_win.findChildren(CalendarDayCell)) > 7


def test_calendar_view_combo_week_and_persists(reminder_ui):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidget

    from taskmanager.ui.reminders_window import CalendarDayCell, RemindersWindow

    window, service, qtbot = reminder_ui
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    assert rem_win.day_pane.isHidden()
    combo = rem_win.calendar_view_combo
    assert combo.isVisible()
    assert combo.parentWidget() is not rem_win.day_pane
    compact_idx = combo.findData("compact")
    assert compact_idx >= 0
    assert combo.itemText(compact_idx) == "Месяц"
    assert combo.currentText() == "Месяц"
    week_idx = combo.findData("week")
    assert week_idx >= 0
    combo.setCurrentIndex(week_idx)
    assert rem_win.day_pane.isHidden()
    assert len(rem_win.findChildren(CalendarDayCell)) == 7
    assert service.settings.calendar_view == "week"
    assert window.settings_store.load().calendar_view == "week"

    compact_idx = combo.findData("compact")
    combo.setCurrentIndex(compact_idx)
    assert rem_win.day_pane.isHidden()
    assert len(rem_win.findChildren(CalendarDayCell)) > 7
    today = date.today()
    cell = rem_win.findChild(QListWidget, f"dayCell_{today.isoformat()}")
    assert cell is not None
    qtbot.mouseClick(cell.viewport(), Qt.MouseButton.LeftButton)
    assert rem_win.day_pane.isVisible()


def test_month_view_dots_without_pane_week_keeps_event_text(reminder_ui):
    from datetime import time as time_cls

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidget

    from taskmanager.ui.reminders_window import RemindersWindow

    window, service, qtbot = reminder_ui
    today = date.today()
    service.create_reminder(
        None,
        text="событие месяца",
        time_of_day=time_cls(11, 0),
        rule=ReminderRule.ONCE,
        once_date=today,
    )
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    assert rem_win.day_pane.isHidden()
    assert rem_win.calendar_view_combo.currentText() == "Месяц"
    cell = rem_win.findChild(QListWidget, f"dayCell_{today.isoformat()}")
    assert cell is not None
    has_dots = False
    for i in range(cell.count()):
        item = cell.item(i)
        assert item.data(Qt.ItemDataRole.UserRole) is None
        assert "событие месяца" not in item.text()
        if cell.itemWidget(item) is not None:
            has_dots = True
    assert has_dots

    rem_win.calendar_view_combo.setCurrentIndex(
        rem_win.calendar_view_combo.findData("week")
    )
    cell = rem_win.findChild(QListWidget, f"dayCell_{today.isoformat()}")
    assert cell is not None
    texts = [cell.item(i).text() for i in range(cell.count())]
    assert any("событие месяца" in text for text in texts)


def _stylesheet_border(ss: str) -> str:
    assert "border:" in ss
    return ss.split("border:", 1)[1].split(";", 1)[0].strip()


def test_day_cell_border_not_transparent_light_and_dark(qtbot):
    from PySide6.QtGui import QColor, QPalette

    from taskmanager.ui.reminders_window import CalendarDayCell

    cell = CalendarDayCell(date.today(), in_month=True)
    qtbot.addWidget(cell)

    light = QPalette(cell.palette())
    light.setColor(QPalette.ColorRole.Window, QColor("#f1f5f9"))
    light.setColor(QPalette.ColorRole.Dark, QColor("#64748b"))
    light.setColor(QPalette.ColorRole.Mid, QColor("#94a3b8"))
    light.setColor(QPalette.ColorRole.Highlight, QColor("#0f766e"))
    cell.setPalette(light)
    cell.apply_chrome(today=False, selected=False, weekend=False)
    ordinary = _stylesheet_border(cell.styleSheet())
    assert "transparent" not in ordinary
    assert light.color(QPalette.ColorRole.Dark).name() in ordinary

    cell.setPalette(light)
    cell.apply_chrome(today=False, selected=True, weekend=False)
    selected = _stylesheet_border(cell.styleSheet())
    assert light.color(QPalette.ColorRole.Highlight).name() in selected
    assert selected != ordinary

    dark = QPalette(cell.palette())
    dark.setColor(QPalette.ColorRole.Window, QColor("#0f172a"))
    dark.setColor(QPalette.ColorRole.Dark, QColor("#1e293b"))
    dark.setColor(QPalette.ColorRole.Mid, QColor("#64748b"))
    dark.setColor(QPalette.ColorRole.Highlight, QColor("#14b8a6"))
    cell.setPalette(dark)
    cell.apply_chrome(today=False, selected=False, weekend=False)
    ordinary_dark = _stylesheet_border(cell.styleSheet())
    assert "transparent" not in ordinary_dark
    assert dark.color(QPalette.ColorRole.Mid).name() in ordinary_dark

    cell.setPalette(dark)
    cell.apply_chrome(today=False, selected=True, weekend=False)
    selected_dark = _stylesheet_border(cell.styleSheet())
    assert dark.color(QPalette.ColorRole.Highlight).name() in selected_dark
    assert selected_dark != ordinary_dark


def test_month_and_week_grid_cells_have_visible_border(reminder_ui):
    from PySide6.QtWidgets import QListWidget

    from taskmanager.ui.reminders_window import CalendarDayCell, RemindersWindow

    window, service, qtbot = reminder_ui
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    today = date.today()
    cell = rem_win.findChild(QListWidget, f"dayCell_{today.isoformat()}")
    assert cell is not None
    assert "transparent" not in _stylesheet_border(cell.styleSheet())
    ordinary = next(
        c
        for c in rem_win.findChildren(CalendarDayCell)
        if not c.property("today") and not c.property("selectedDay")
    )
    assert "transparent" not in _stylesheet_border(ordinary.styleSheet())

    rem_win.calendar_view_combo.setCurrentIndex(
        rem_win.calendar_view_combo.findData("week")
    )
    week_cell = rem_win.findChild(QListWidget, f"dayCell_{today.isoformat()}")
    assert week_cell is not None
    assert "transparent" not in _stylesheet_border(week_cell.styleSheet())


def test_format_day_heading_relative_to_today():
    from datetime import timedelta

    from taskmanager.ui.reminders_window import _format_day_heading

    today = date(2026, 8, 18)
    heading = _format_day_heading(today, today=today)
    assert "назад" not in heading
    assert "через" not in heading
    assert "18" in heading
    assert "августа" in heading

    yesterday = _format_day_heading(today - timedelta(days=1), today=today)
    assert "1 день назад" in yesterday
    assert "через" not in yesterday

    after = _format_day_heading(today + timedelta(days=2), today=today)
    assert "через 2 дня" in after
    assert "назад" not in after

    five = _format_day_heading(today - timedelta(days=5), today=today)
    assert "5 дней назад" in five


def test_day_pane_heading_shows_relative_offset(reminder_ui):
    from datetime import timedelta

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidget

    from taskmanager.ui.reminders_window import RemindersWindow

    window, service, qtbot = reminder_ui
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    today = date.today()
    yesterday = today - timedelta(days=1)
    later = today + timedelta(days=2)

    def heading_for(day: date) -> str:
        rem_win._year = day.year
        rem_win._month = day.month
        rem_win.reload()
        cell = rem_win.findChild(QListWidget, f"dayCell_{day.isoformat()}")
        assert cell is not None
        qtbot.mouseClick(cell.viewport(), Qt.MouseButton.LeftButton)
        return rem_win.day_pane_title.text()

    past = heading_for(yesterday)
    assert "1 день назад" in past
    assert "через" not in past
    future = heading_for(later)
    assert "через 2 дня" in future
    assert "назад" not in future


def test_week_view_day_click_opens_pane_and_card_from_pane(reminder_ui):
    from datetime import time as time_cls

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QListWidget

    from taskmanager.ui.reminders_window import (
        ReminderCardDialog,
        ReminderEditDialog,
        RemindersWindow,
    )

    window, service, qtbot = reminder_ui
    today = date.today()
    service.create_reminder(
        None,
        text="в панели недели",
        time_of_day=time_cls(10, 0),
        rule=ReminderRule.ONCE,
        once_date=today,
    )
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    rem_win.calendar_view_combo.setCurrentIndex(
        rem_win.calendar_view_combo.findData("week")
    )
    assert rem_win.day_pane.isHidden()
    cell = rem_win.findChild(QListWidget, f"dayCell_{today.isoformat()}")
    assert cell is not None
    qtbot.mouseClick(cell.viewport(), Qt.MouseButton.LeftButton)
    assert rem_win.day_pane.isVisible()
    assert rem_win.day_events.count() == 1
    assert "в панели недели" in rem_win.day_events.item(0).text()
    cell = rem_win.findChild(QListWidget, f"dayCell_{today.isoformat()}")
    assert cell is not None
    assert cell.property("selectedDay") is True

    captured: list[date] = []

    def grab_and_reject() -> None:
        edits = rem_win.findChildren(ReminderEditDialog)
        assert edits
        captured.append(edits[0].once_date_value)
        edits[0].reject()

    QTimer.singleShot(0, grab_and_reject)
    rem_win.create_event_btn.click()
    assert captured == [today]

    rem_win.day_events.itemDoubleClicked.emit(rem_win.day_events.item(0))
    cards = [c for c in rem_win.findChildren(ReminderCardDialog) if c.isVisible()]
    assert cards
    assert "в панели недели" in cards[-1].body_label.toPlainText()


def test_week_view_changing_day_does_not_reset_splitter(reminder_ui):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidget

    from taskmanager.ui.reminders_window import CalendarDayCell, RemindersWindow

    window, service, qtbot = reminder_ui
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    rem_win.resize(1100, 720)
    rem_win.calendar_view_combo.setCurrentIndex(
        rem_win.calendar_view_combo.findData("week")
    )
    cells = rem_win.findChildren(CalendarDayCell)
    assert len(cells) == 7
    first = cells[0].day
    other = next(cell.day for cell in cells if cell.day != first)
    cell = rem_win.findChild(QListWidget, f"dayCell_{first.isoformat()}")
    assert cell is not None
    qtbot.mouseClick(cell.viewport(), Qt.MouseButton.LeftButton)
    assert rem_win.day_pane.isVisible()
    rem_win.calendar_splitter.setSizes([220, 500])
    sizes = rem_win.calendar_splitter.sizes()
    other_cell = rem_win.findChild(QListWidget, f"dayCell_{other.isoformat()}")
    assert other_cell is not None
    qtbot.mouseClick(other_cell.viewport(), Qt.MouseButton.LeftButton)
    assert rem_win.day_pane.isVisible()
    assert rem_win.calendar_splitter.sizes() == sizes
    assert rem_win.day_pane_title.text()
    assert str(other.day) in rem_win.day_pane_title.text()


def test_week_view_opens_pane_split_in_half(reminder_ui):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidget

    from taskmanager.ui.reminders_window import RemindersWindow

    window, service, qtbot = reminder_ui
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    rem_win.resize(1100, 720)
    rem_win.calendar_view_combo.setCurrentIndex(
        rem_win.calendar_view_combo.findData("week")
    )
    today = date.today()
    cell = rem_win.findChild(QListWidget, f"dayCell_{today.isoformat()}")
    assert cell is not None
    qtbot.mouseClick(cell.viewport(), Qt.MouseButton.LeftButton)
    assert rem_win.day_pane.isVisible()
    sizes = rem_win.calendar_splitter.sizes()
    total = sum(sizes)
    assert total > 0
    assert abs(sizes[0] - sizes[1]) <= total * 0.2


def test_calendar_close_hides_window_even_if_day_pane_open(reminder_ui):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidget

    from taskmanager.ui.reminders_window import RemindersWindow

    window, service, qtbot = reminder_ui
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    today = date.today()
    cell = rem_win.findChild(QListWidget, f"dayCell_{today.isoformat()}")
    assert cell is not None
    qtbot.mouseClick(cell.viewport(), Qt.MouseButton.LeftButton)
    assert rem_win.day_pane.isVisible()
    assert rem_win.isVisible()
    rem_win.reject()
    assert rem_win.isHidden()
    assert not rem_win.day_pane.isHidden()


def test_calendar_layout_persists_view_splitter_and_open_pane(reminder_ui):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidget

    from taskmanager.ui.reminders_window import RemindersWindow

    window, service, qtbot = reminder_ui
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    rem_win.resize(1100, 720)
    rem_win.calendar_view_combo.setCurrentIndex(
        rem_win.calendar_view_combo.findData("week")
    )
    today = date.today()
    cell = rem_win.findChild(QListWidget, f"dayCell_{today.isoformat()}")
    assert cell is not None
    qtbot.mouseClick(cell.viewport(), Qt.MouseButton.LeftButton)
    rem_win.calendar_splitter.setSizes([220, 500])
    wanted = rem_win.calendar_splitter.sizes()
    rem_win.reject()

    loaded = window.settings_store.load()
    assert loaded.calendar_view == "week"
    assert loaded.calendar_day_pane_open is True
    assert loaded.calendar_week_splitter == list(wanted)

    again = RemindersWindow(service, window)
    qtbot.addWidget(again)
    again.show()
    again.resize(1100, 720)
    assert again.calendar_view_combo.currentData() == "week"
    assert again.day_pane.isVisible()
    restored = again.calendar_splitter.sizes()
    assert sum(restored) > 0
    assert abs(restored[0] / sum(restored) - wanted[0] / sum(wanted)) < 0.12


def test_weekend_cells_use_weekend_wash_not_today(reminder_ui):
    from datetime import timedelta

    from PySide6.QtWidgets import QListWidget

    from taskmanager.ui.reminders_window import RemindersWindow

    window, service, qtbot = reminder_ui
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    today = date.today()
    today_cell = rem_win.findChild(QListWidget, f"dayCell_{today.isoformat()}")
    assert today_cell is not None
    weekend_cell = None
    monday = today - timedelta(days=today.weekday())
    for offset in range(0, 21):
        day = monday + timedelta(days=offset)
        if day.weekday() not in (5, 6) or day == today:
            continue
        found = rem_win.findChild(QListWidget, f"dayCell_{day.isoformat()}")
        if found is not None:
            weekend_cell = found
            break
    assert weekend_cell is not None
    assert weekend_cell.property("weekend") is True
    assert weekend_cell.property("today") is False
    assert today_cell.property("today") is True
    assert weekend_cell.styleSheet() != today_cell.styleSheet()


def test_notify_dismiss_stops_sound_player(reminder_ui, monkeypatch):
    from datetime import timedelta

    from taskmanager.domain import ReminderRule
    from taskmanager.ui.reminders_window import ReminderNotifyDialog

    window, service, qtbot = reminder_ui
    occ = datetime.now().replace(second=0, microsecond=0) - timedelta(hours=1)
    series = service.create_reminder(
        None,
        text="стоп звука",
        time_of_day=occ.time(),
        rule=ReminderRule.ONCE,
        once_date=occ.date(),
    )
    stops: list[int] = []
    original_stop = window._event_sound_player.stop

    def spy_stop() -> None:
        stops.append(1)
        original_stop()

    monkeypatch.setattr(window._event_sound_player, "stop", spy_stop)
    window._notify_reminder(series, occ, None, None)
    popup = [
        w for w in window.findChildren(ReminderNotifyDialog) if w.isVisible()
    ][-1]
    stops.clear()
    popup.accept()
    assert stops

    window._notify_reminder(series, occ, None, None)
    popup = [
        w for w in window.findChildren(ReminderNotifyDialog) if w.isVisible()
    ][-1]
    stops.clear()
    popup.reject()
    assert stops

    window._notify_reminder(series, occ, None, None)
    popup = [
        w for w in window.findChildren(ReminderNotifyDialog) if w.isVisible()
    ][-1]
    stops.clear()
    popup._snooze()
    assert stops


def _past_once_event(service: TaskService, text: str, *, hours_ago: int, task_id=None):
    from datetime import timedelta

    occ = datetime.now().replace(second=0, microsecond=0) - timedelta(hours=hours_ago)
    return service.create_reminder(
        task_id,
        text=text,
        time_of_day=occ.time(),
        rule=ReminderRule.ONCE,
        once_date=occ.date(),
    )


def _missed_button(win, text: str):
    from PySide6.QtWidgets import QPushButton

    for btn in win.missed_page.findChildren(QPushButton):
        if btn.text() == text:
            return btn
    raise AssertionError(f"button {text!r} not found")


def test_missed_click_selects_double_click_opens_card(reminder_ui):
    from taskmanager.ui.reminders_window import ReminderCardDialog, RemindersWindow

    window, service, qtbot = reminder_ui
    _past_once_event(service, "одиночный клик", hours_ago=1)
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    rem_win.tabs.setCurrentWidget(rem_win.missed_page)
    assert rem_win.missed_list.count() == 1
    item = rem_win.missed_list.item(0)
    rem_win.missed_list.itemClicked.emit(item)
    cards = [c for c in rem_win.findChildren(ReminderCardDialog) if c.isVisible()]
    assert cards == []
    rem_win.missed_list.itemDoubleClicked.emit(item)
    cards = [c for c in rem_win.findChildren(ReminderCardDialog) if c.isVisible()]
    assert cards
    assert "одиночный клик" in cards[-1].body_label.toPlainText()


def test_missed_ack_applies_to_all_selected(reminder_ui):
    window, service, qtbot = reminder_ui
    a = _past_once_event(service, "ack-a", hours_ago=3)
    b = _past_once_event(service, "ack-b", hours_ago=2)
    c = _past_once_event(service, "ack-c", hours_ago=1)
    from taskmanager.ui.reminders_window import RemindersWindow

    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    rem_win.tabs.setCurrentWidget(rem_win.missed_page)
    assert rem_win.missed_list.count() == 3
    ack = _missed_button(rem_win, "Подтвердить")
    assert not ack.isEnabled()

    rem_win.missed_list.clearSelection()
    rem_win.missed_list.item(0).setSelected(True)
    rem_win.missed_list.item(1).setSelected(True)
    assert ack.isEnabled()
    ack.click()
    assert rem_win.missed_list.count() == 1
    remaining = {row[0].id for row in service.list_missed_reminders()}
    assert remaining == {c.id}
    assert service.get_reminder(a.id) is not None
    assert service.get_reminder(b.id) is not None


def test_missed_delete_selected_asks_count_and_deletes_series(reminder_ui, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from taskmanager.ui.reminders_window import RemindersWindow

    window, service, qtbot = reminder_ui
    a = _past_once_event(service, "del-a", hours_ago=2)
    b = _past_once_event(service, "del-b", hours_ago=1)
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    rem_win.tabs.setCurrentWidget(rem_win.missed_page)
    rem_win.missed_list.clearSelection()
    rem_win.missed_list.item(0).setSelected(True)
    rem_win.missed_list.item(1).setSelected(True)
    prompts: list[str] = []

    def capture_question(*args, **kwargs):
        prompts.append(args[2] if len(args) > 2 else "")
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", capture_question)
    _missed_button(rem_win, "Удалить событие").click()
    assert prompts == ["Удалить 2 событий?"]
    assert rem_win.missed_list.count() == 0
    assert service.list_reminders() == []
    assert service.repo.get_reminder(a.id) is None
    assert service.repo.get_reminder(b.id) is None


def test_missed_ack_all(reminder_ui):
    from PySide6.QtWidgets import QMessageBox

    from taskmanager.ui.reminders_window import RemindersWindow

    window, service, qtbot = reminder_ui
    _past_once_event(service, "all-a", hours_ago=3)
    _past_once_event(service, "all-b", hours_ago=2)
    keep = _past_once_event(service, "all-c", hours_ago=1)
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    rem_win.tabs.setCurrentWidget(rem_win.missed_page)
    assert rem_win.missed_list.count() == 3
    ack_all = _missed_button(rem_win, "Подтвердить всё")
    delete_all = _missed_button(rem_win, "Удалить всё")
    select_all = _missed_button(rem_win, "Выбрать все")
    assert ack_all.isEnabled()
    assert delete_all.isEnabled()
    assert select_all.isEnabled()

    rem_win.missed_list.item(0).setSelected(True)
    ack_all.click()
    assert rem_win.missed_list.count() == 0
    assert service.list_missed_reminders() == []
    assert len(service.list_reminders()) == 3
    assert keep.id in {row.id for row in service.list_reminders()}
    assert not ack_all.isEnabled()
    assert not delete_all.isEnabled()
    assert not select_all.isEnabled()


def test_missed_delete_all_asks_count_and_deletes_series(reminder_ui, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from taskmanager.ui.reminders_window import RemindersWindow

    window, service, qtbot = reminder_ui
    _past_once_event(service, "wipe-a", hours_ago=2)
    _past_once_event(service, "wipe-b", hours_ago=1)
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    rem_win.tabs.setCurrentWidget(rem_win.missed_page)
    delete_all = _missed_button(rem_win, "Удалить всё")
    assert rem_win.missed_list.count() == 2
    prompts: list[str] = []

    def capture_question(*args, **kwargs):
        prompts.append(args[2] if len(args) > 2 else "")
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", capture_question)
    delete_all.click()
    assert prompts == ["Удалить 2 событий?"]
    assert rem_win.missed_list.count() == 0
    assert service.list_reminders() == []
    assert not delete_all.isEnabled()


def test_missed_select_all_and_open_task_enabled_for_single_linked(reminder_ui):
    from taskmanager.ui.reminders_window import RemindersWindow

    window, service, qtbot = reminder_ui
    project = service.create_project("MissedBulk")
    task = service.create_task(
        CreateTaskRequest(project_id=project.id, number="31", create_folder=False)
    )
    _past_once_event(service, "linked", hours_ago=2, task_id=task.id)
    _past_once_event(service, "standalone", hours_ago=1)
    rem_win = RemindersWindow(service, window)
    qtbot.addWidget(rem_win)
    rem_win.show()
    rem_win.tabs.setCurrentWidget(rem_win.missed_page)
    select_all = _missed_button(rem_win, "Выбрать все")
    open_task = _missed_button(rem_win, "Открыть заявку")
    skip = _missed_button(rem_win, "Пропустить вхождение")
    assert rem_win.missed_list.count() == 2
    assert rem_win.missed_list.selectedItems() == []
    assert not open_task.isEnabled()
    assert not skip.isEnabled()

    select_all.click()
    assert len(rem_win.missed_list.selectedItems()) == 2
    assert skip.isEnabled()
    assert not open_task.isEnabled()

    rem_win.missed_list.clearSelection()
    for i in range(rem_win.missed_list.count()):
        item = rem_win.missed_list.item(i)
        if "linked" in item.text() or "31" in item.text():
            item.setSelected(True)
            break
    assert open_task.isEnabled()
    opened: list[int] = []
    rem_win.open_task_requested.connect(opened.append)
    open_task.click()
    assert opened == [task.id]

    select_all.click()
    skip.click()
    assert rem_win.missed_list.count() == 0
    assert service.list_missed_reminders() == []
    assert len(service.list_reminders()) == 2


def test_event_add_custom_color_saved_and_in_task_palette(reminder_ui, monkeypatch):
    import json

    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QColorDialog, QToolButton

    from taskmanager.ui.reminders_window import ReminderEditDialog

    window, service, qtbot = reminder_ui
    dialog = ReminderEditDialog(service, window)
    qtbot.addWidget(dialog)

    add_buttons = [
        btn
        for btn in dialog.findChildren(QToolButton)
        if btn.text() == "+"
    ]
    assert add_buttons, "Event form should have a + color button"
    monkeypatch.setattr(
        QColorDialog, "getColor", lambda *a, **k: QColor("#123456")
    )
    add_buttons[0].click()
    assert "#123456" in service.settings.colors.values()
    saved = json.loads(window.settings_store.path.read_text(encoding="utf-8"))
    assert "#123456" in saved.get("colors", {}).values()
    tooltips = [
        btn.toolTip() for btn in window.palette_host.findChildren(QToolButton)
    ]
    assert any("123456" in tip.lower() for tip in tooltips)


def test_notify_queues_second_ping_until_current_closes(reminder_ui, monkeypatch):
    from datetime import timedelta

    from taskmanager.domain import ReminderRule
    from taskmanager.ui.reminders_window import ReminderNotifyDialog

    window, service, qtbot = reminder_ui
    occ = datetime.now().replace(second=0, microsecond=0) - timedelta(hours=1)
    first = service.create_reminder(
        None,
        text="первый пинг",
        time_of_day=occ.time(),
        rule=ReminderRule.ONCE,
        once_date=occ.date(),
    )
    later = occ.replace(minute=(occ.minute + 1) % 60)
    second = service.create_reminder(
        None,
        text="второй пинг",
        time_of_day=later.time(),
        rule=ReminderRule.ONCE,
        once_date=later.date(),
    )
    played: list[str] = []
    monkeypatch.setattr(
        window._event_sound_player, "play", lambda path: played.append(path)
    )
    window.settings.event_sound_enabled = True
    window.settings.event_sound_path = "/settings/ding.wav"
    window._notify_reminder(first, occ, None, None)
    window._notify_reminder(second, later, None, None)
    visible = [
        w for w in window.findChildren(ReminderNotifyDialog) if w.isVisible()
    ]
    assert len(visible) == 1
    assert "первый пинг" in visible[0].body_edit.toPlainText()
    assert played == ["/settings/ding.wav", "/settings/ding.wav"]
    visible[0].accept()
    visible = [
        w for w in window.findChildren(ReminderNotifyDialog) if w.isVisible()
    ]
    assert len(visible) == 1
    assert "второй пинг" in visible[0].body_edit.toPlainText()


def test_notify_ping_clickable_over_task_dialog(reminder_ui, monkeypatch):
    from datetime import timedelta

    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QApplication

    from taskmanager.domain import ReminderRule
    from taskmanager.ui.dialogs import TaskDialog
    from taskmanager.ui.reminders_window import ReminderNotifyDialog

    window, service, qtbot = reminder_ui
    project = service.create_project("ModalPing")
    task = service.create_task(
        CreateTaskRequest(
            project_id=project.id, number="31", create_folder=False
        )
    )
    occ = datetime.now().replace(second=0, microsecond=0) - timedelta(hours=1)
    series = service.create_reminder(
        task.id,
        text="пинг поверх",
        time_of_day=occ.time(),
        rule=ReminderRule.ONCE,
        once_date=occ.date(),
    )
    window.reload_projects()
    dialog = TaskDialog(window.settings, window, task=task)
    dialog.comment_row.html = "<p>черновик</p>"
    opened: list[int] = []
    monkeypatch.setattr(window, "edit_selected_task", lambda: opened.append(1))
    original_reveal = window.reveal_task
    seen: dict[str, object] = {}

    def spy_reveal(task_id: int) -> None:
        original_reveal(task_id)
        seen["revealed"] = task_id
        seen["selected"] = window.selected_task_ids()

    monkeypatch.setattr(window, "reveal_task", spy_reveal)

    def fire() -> None:
        assert QApplication.activeModalWidget() is dialog
        window._notify_reminder(series, occ, task, project)
        popups = [
            w for w in window.findChildren(ReminderNotifyDialog) if w.isVisible()
        ]
        assert popups
        popup = popups[-1]
        seen["modality"] = popup.windowModality()
        assert popup.open_task_btn.isEnabled()
        popup.open_task_btn.click()
        seen["comment"] = dialog.comment
        dialog.reject()

    QTimer.singleShot(0, fire)
    dialog.exec()
    assert seen["modality"] == Qt.WindowModality.ApplicationModal
    assert "черновик" in str(seen["comment"])
    assert seen["revealed"] == task.id
    assert seen["selected"] == [task.id]
    assert opened == []



