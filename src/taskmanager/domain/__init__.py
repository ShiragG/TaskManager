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


PRIORITY_MIN = 0
PRIORITY_MAX = 10
PRIORITY_DEFAULT = 10


def clamp_priority(value: int) -> int:
    """Clamp priority to the inclusive 0–10 range."""
    return max(PRIORITY_MIN, min(PRIORITY_MAX, int(value)))


def priority_color_hex(priority: int) -> str:
    """RGB hex for the priority scale: 0 red → 5 yellow → 10 green."""
    p = clamp_priority(priority)
    if p <= 5:
        t = p / 5
        r, g, b = 255, int(255 * t), 0
    else:
        t = (p - 5) / 5
        r, g, b = int(255 * (1 - t)), 255, 0
    return f"#{r:02x}{g:02x}{b:02x}"


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
    priority: int = PRIORITY_DEFAULT
    hidden: bool = False
    archive_month: str | None = None
    created_at: datetime | None = None
    links: list[Link] = field(default_factory=list)

    @property
    def is_archived(self) -> bool:
        return self.status == TaskStatus.ARCHIVED
