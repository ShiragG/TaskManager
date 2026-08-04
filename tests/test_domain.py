from datetime import date

from taskmanager.domain import is_deadline_warning, make_folder_name, sanitize_for_folder


def test_make_folder_name_is_number_only():
    assert make_folder_name("123") == "123"
    assert make_folder_name("  42  ") == "42"


def test_make_folder_name_sanitizes():
    assert make_folder_name("a:b/c") == "abc"


def test_sanitize_strips_forbidden():
    assert ":" not in sanitize_for_folder("a:b/c")
    assert "___" not in sanitize_for_folder("x___y")


def test_is_deadline_warning_lead_days():
    today = date(2026, 8, 5)
    assert is_deadline_warning(date(2026, 8, 5), today=today, lead_days=1)
    assert is_deadline_warning(date(2026, 8, 6), today=today, lead_days=1)
    assert not is_deadline_warning(date(2026, 8, 7), today=today, lead_days=1)
    assert is_deadline_warning(date(2026, 8, 1), today=today, lead_days=1)
    assert not is_deadline_warning(None, today=today, lead_days=1)
