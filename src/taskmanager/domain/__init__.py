from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum
import re

from PySide6.QtGui import QTextDocument

from taskmanager.domain.reminders import (
    PLAIN_CELL_LIMIT,
    ReminderRule,
    ReminderSeries,
    WEEKDAY_LABELS,
    acknowledge_series,
    last_occurrence,
    missed_occurrence,
    occurrence_on,
    occurrences_in_range,
    parse_reminder_rule,
    parse_whole_number,
    skip_occurrence,
    truncate_plain,
)


class TaskStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class WorkflowStatus(StrEnum):
    """Local work progress for Tasks without a source link."""

    NEW = "new"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    DONE = "done"
    CANCELLED = "cancelled"


WORKFLOW_STATUS_LABELS: dict[WorkflowStatus, str] = {
    WorkflowStatus.NEW: "Новая",
    WorkflowStatus.IN_PROGRESS: "В работе",
    WorkflowStatus.WAITING: "Ждёт",
    WorkflowStatus.DONE: "Готово",
    WorkflowStatus.CANCELLED: "Отменена",
}


def parse_workflow_status(value: str | None) -> WorkflowStatus:
    if not value:
        return WorkflowStatus.NEW
    try:
        return WorkflowStatus(value)
    except ValueError:
        return WorkflowStatus.NEW


def workflow_status_label(value: str | WorkflowStatus | None) -> str:
    status = (
        value
        if isinstance(value, WorkflowStatus)
        else parse_workflow_status(value)
    )
    return WORKFLOW_STATUS_LABELS[status]


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


_NAT_CHUNK_RE = re.compile(r"(\d+)|(\D+)")


def natural_sort_key(text: str) -> tuple[tuple[int, int | str], ...]:
    """Sort key: digit runs as int, other runs as casefolded text.

    ``2`` < ``2а`` < ``10`` < ``10а``; mixed ids such as ``INC-9`` < ``INC-10``.
    """
    parts: list[tuple[int, int | str]] = []
    for digits, rest in _NAT_CHUNK_RE.findall(text):
        if digits:
            parts.append((0, int(digits)))
        else:
            parts.append((1, rest.casefold()))
    return tuple(parts)


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


_HREF_RE = re.compile(
    r"""<a\b[^>]*\bhref\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)


def html_to_plain(html: str) -> str:
    """Plain-text preview from stored HTML via QTextDocument (no CSS leftovers)."""
    if not html:
        return ""
    doc = QTextDocument()
    doc.setHtml(html)
    return " ".join(doc.toPlainText().split())


def html_to_plain_with_urls(html: str) -> str:
    """Plain text plus href URLs that are not already visible in the text."""
    plain = html_to_plain(html)
    if not html:
        return plain
    urls: list[str] = []
    for match in _HREF_RE.finditer(html):
        url = match.group(1).strip()
        if url and url not in plain and url not in urls:
            urls.append(url)
    if not urls:
        return plain
    suffix = " ".join(urls)
    return f"{plain} {suffix}".strip() if plain else suffix


def contrast_foreground(bg_hex: str) -> str:
    """Return near-black or near-white hex for readable text on ``bg_hex``."""
    raw = bg_hex.lstrip("#")
    if len(raw) == 3:
        raw = "".join(c * 2 for c in raw)
    if len(raw) != 6:
        return "#0f172a"
    try:
        r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except ValueError:
        return "#0f172a"
    # Relative luminance (sRGB approximation)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#0f172a" if luminance > 0.55 else "#f8fafc"


@dataclass(frozen=True)
class Project:
    id: int | None
    name: str
    sort_order: int = 0
    number_high_water: int = 0


@dataclass
class Link:
    id: int | None
    task_id: int | None
    name: str
    target: str


@dataclass
class Task:
    id: int | None
    project_id: int
    number: str
    description: str
    folder_name: str
    status: TaskStatus = TaskStatus.ACTIVE
    date_end: date | None = None
    color: str | None = None
    comment: str = ""
    priority: int = PRIORITY_DEFAULT
    hidden: bool = False
    has_folder: bool = True
    archive_month: str | None = None
    archive_project_folder: str | None = None
    created_at: datetime | None = None
    links: list[Link] = field(default_factory=list)
    source_module_id: str | None = None
    external_id: str | None = None
    source_label: str | None = None
    workflow_status: WorkflowStatus = WorkflowStatus.NEW
    source_status_id: str | None = None
    source_status_label: str | None = None
    description_plain: str = ""
    comment_plain: str = ""

    @property
    def is_archived(self) -> bool:
        return self.status == TaskStatus.ARCHIVED

    @property
    def has_source(self) -> bool:
        return bool(self.source_module_id and self.external_id)

    @property
    def display_status(self) -> str:
        """Single UI status column: Source snapshot when linked, else Workflow."""
        if self.has_source:
            label = (self.source_status_label or "").strip()
            if label:
                return label
            return (self.source_status_id or "").strip()
        return workflow_status_label(self.workflow_status)
