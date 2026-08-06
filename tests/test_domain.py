from datetime import date

from taskmanager.domain import (
    contrast_foreground,
    html_to_plain,
    is_deadline_warning,
    make_folder_name,
    sanitize_for_folder,
)


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


def test_html_to_plain():
    assert html_to_plain("<b>Hello</b> &amp; world") == "Hello & world"
    assert html_to_plain("") == ""


def test_html_to_plain_with_urls():
    from taskmanager.domain import html_to_plain_with_urls

    assert (
        html_to_plain_with_urls('<a href="https://ex.com">click</a>')
        == "click https://ex.com"
    )
    assert (
        html_to_plain_with_urls('<a href="https://ex.com">https://ex.com</a>')
        == "https://ex.com"
    )
    assert html_to_plain_with_urls("") == ""


def test_contrast_foreground():
    assert contrast_foreground("#ffffff") == "#0f172a"
    assert contrast_foreground("#000000") == "#f8fafc"
