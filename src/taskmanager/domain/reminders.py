"""Reminder series, occurrence rules, and missed detection (no Qt)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import StrEnum


class ReminderRule(StrEnum):
    ONCE = "once"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# Monday=0 … Sunday=6, matching datetime.date.weekday().
WEEKDAY_LABELS: tuple[str, ...] = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


@dataclass
class ReminderSeries:
    id: int | None
    task_id: int | None
    text: str
    time_of_day: time
    rule: ReminderRule
    once_date: date | None = None
    weekdays: tuple[int, ...] = ()
    month_day: int | None = None
    last_acknowledged_occurrence: datetime | None = None
    skipped_occurrences: tuple[datetime, ...] = field(default_factory=tuple)

    @property
    def is_repeating(self) -> bool:
        return self.rule != ReminderRule.ONCE


def parse_reminder_rule(value: str | ReminderRule | None) -> ReminderRule:
    if isinstance(value, ReminderRule):
        return value
    try:
        return ReminderRule(value or ReminderRule.ONCE)
    except ValueError:
        return ReminderRule.ONCE


def _combine(day: date, clock: time) -> datetime:
    return datetime(
        day.year,
        day.month,
        day.day,
        clock.hour,
        clock.minute,
        clock.second,
        clock.microsecond,
    )


def occurrence_on(series: ReminderSeries, day: date) -> datetime | None:
    """Local datetime if the series fires on ``day``; None if that day is skipped by the rule."""
    clock = series.time_of_day
    if series.rule == ReminderRule.ONCE:
        if series.once_date is None or day != series.once_date:
            return None
        return _combine(day, clock)
    if series.rule == ReminderRule.WEEKLY:
        if day.weekday() not in series.weekdays:
            return None
        return _combine(day, clock)
    if series.rule == ReminderRule.MONTHLY:
        if series.month_day is None:
            return None
        try:
            scheduled = date(day.year, day.month, series.month_day)
        except ValueError:
            return None
        if day != scheduled:
            return None
        return _combine(day, clock)
    return None


def occurrences_in_range(
    series: ReminderSeries,
    start: date,
    end: date,
) -> list[datetime]:
    """Inclusive date range; short months with no matching day contribute nothing."""
    if end < start:
        return []
    found: list[datetime] = []
    day = start
    one = timedelta(days=1)
    while day <= end:
        occ = occurrence_on(series, day)
        if occ is not None:
            found.append(occ)
        day += one
    return found


def last_occurrence(series: ReminderSeries, now: datetime) -> datetime | None:
    """Latest occurrence at or before ``now``, or None if none exists yet."""
    if series.rule == ReminderRule.ONCE:
        if series.once_date is None:
            return None
        occ = occurrence_on(series, series.once_date)
        if occ is None or occ > now:
            return None
        return occ

    if series.rule == ReminderRule.WEEKLY:
        if not series.weekdays:
            return None
        for offset in range(0, 8):
            day = now.date() - timedelta(days=offset)
            occ = occurrence_on(series, day)
            if occ is not None and occ <= now:
                return occ
        return None

    if series.rule == ReminderRule.MONTHLY:
        if series.month_day is None:
            return None
        year, month = now.year, now.month
        for _ in range(24):
            try:
                day = date(year, month, series.month_day)
            except ValueError:
                day = None
            if day is not None:
                occ = _combine(day, series.time_of_day)
                if occ <= now:
                    return occ
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        return None

    return None


def _is_skipped(series: ReminderSeries, occ: datetime) -> bool:
    return occ in series.skipped_occurrences


def _is_acknowledged(series: ReminderSeries, occ: datetime) -> bool:
    acked = series.last_acknowledged_occurrence
    return acked is not None and acked >= occ


def missed_occurrence(series: ReminderSeries, now: datetime) -> datetime | None:
    """Latest past occurrence that is neither skipped nor acknowledged."""
    occ = last_occurrence(series, now)
    if occ is None:
        return None
    if _is_skipped(series, occ) or _is_acknowledged(series, occ):
        return None
    return occ


def acknowledge_series(series: ReminderSeries, occ: datetime) -> ReminderSeries:
    """Mark ``occ`` acknowledged; it stays a calendar occurrence."""
    series.last_acknowledged_occurrence = occ
    return series


def skip_occurrence(series: ReminderSeries, occ: datetime) -> ReminderSeries:
    if occ not in series.skipped_occurrences:
        series.skipped_occurrences = (*series.skipped_occurrences, occ)
    return series


PLAIN_CELL_LIMIT = 120


def truncate_plain(text: str, limit: int = PLAIN_CELL_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def parse_whole_number(text: str) -> int | None:
    """Return int if ``text`` is a whole number (digits only), else None."""
    stripped = text.strip()
    if not stripped or not stripped.isdigit():
        return None
    return int(stripped)
