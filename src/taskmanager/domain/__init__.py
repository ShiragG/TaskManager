from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum


class TaskStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


FORBIDDEN_PATH_CHARS = '\\/:*?"<>|()'


def sanitize_for_folder(text: str) -> str:
    """Remove characters that are unsafe in folder names."""
    result = text
    for ch in FORBIDDEN_PATH_CHARS:
        result = result.replace(ch, "")
    return result.replace("___", "_")


def make_folder_name(number: str) -> str:
    """On-disk folder name equals the sanitized task number."""
    return sanitize_for_folder(number.strip())


def is_deadline_warning(
    date_end: date | None,
    *,
    today: date,
    lead_days: int,
) -> bool:
    """True when date_end is set and falls on or before today + lead_days."""
    if date_end is None:
        return False
    return date_end <= today + timedelta(days=lead_days)


@dataclass(frozen=True)
class Directory:
    id: int | None
    name: str
    sort_order: int = 0


@dataclass
class Link:
    id: int | None
    task_id: int | None
    name: str
    target: str


@dataclass
class Task:
    id: int | None
    directory_id: int
    number: str
    description: str
    folder_name: str
    status: TaskStatus = TaskStatus.ACTIVE
    date_end: date | None = None
    color: str = "#ffffff"
    hidden: bool = False
    archive_month: str | None = None
    created_at: datetime | None = None
    links: list[Link] = field(default_factory=list)

    @property
    def is_archived(self) -> bool:
        return self.status == TaskStatus.ARCHIVED
