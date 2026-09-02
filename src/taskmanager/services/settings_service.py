from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from taskmanager.infrastructure.event_sounds import parse_event_sound_path
from taskmanager.infrastructure.paths import resolve_work_dir
from taskmanager.services.hotkeys import default_hotkeys_copy, normalize_hotkeys


DEFAULT_COLORS = {
    "Белый": "#ffffff",
    "Красный": "#ff0000",
    "Зелёный": "#99ff66",
    "Жёлтый": "#ffff00",
}

BASE_COLOR_NAMES = frozenset(DEFAULT_COLORS.keys())

THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_SYSTEM = "system"
THEME_MODES = frozenset({THEME_LIGHT, THEME_DARK, THEME_SYSTEM})

SNOOZE_MINUTES: tuple[int, ...] = (1, 5, 10, 15, 30, 60, 120, 180)
SNOOZE_LABELS: dict[int, str] = {
    1: "1 мин",
    5: "5 мин",
    10: "10 мин",
    15: "15 мин",
    30: "30 мин",
    60: "1 ч",
    120: "2 ч",
    180: "3 ч",
}
DEFAULT_SNOOZE_MINUTES = 15

CALENDAR_VIEW_COMPACT = "compact"
CALENDAR_VIEW_WEEK = "week"
CALENDAR_VIEWS = frozenset({CALENDAR_VIEW_COMPACT, CALENDAR_VIEW_WEEK})

IMAGE_PREVIEW_SMALL = 240
IMAGE_PREVIEW_MEDIUM = 480
IMAGE_PREVIEW_ORIGINAL = 0
IMAGE_PREVIEW_WIDTHS = frozenset(
    {IMAGE_PREVIEW_SMALL, IMAGE_PREVIEW_MEDIUM, IMAGE_PREVIEW_ORIGINAL}
)
DEFAULT_IMAGE_PREVIEW_WIDTH = IMAGE_PREVIEW_MEDIUM


def parse_snooze_minutes(value: Any) -> int:
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return DEFAULT_SNOOZE_MINUTES
    if minutes in SNOOZE_MINUTES:
        return minutes
    return DEFAULT_SNOOZE_MINUTES


def parse_calendar_view(value: Any) -> str:
    if value in CALENDAR_VIEWS:
        return str(value)
    return CALENDAR_VIEW_COMPACT


def parse_image_preview_width(value: Any) -> int:
    try:
        width = int(value)
    except (TypeError, ValueError):
        return DEFAULT_IMAGE_PREVIEW_WIDTH
    if width in IMAGE_PREVIEW_WIDTHS:
        return width
    return DEFAULT_IMAGE_PREVIEW_WIDTH


def parse_splitter_sizes(value: Any) -> list[int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return []
    try:
        first = int(value[0])
        second = int(value[1])
    except (TypeError, ValueError):
        return []
    if first < 1 or second < 1:
        return []
    return [first, second]


@dataclass
class SourceModuleConfig:
    """Per-module registry row (credentials live encrypted in SQLite)."""

    github_repo: str = ""
    enabled: bool = False
    module_id: str = ""
    display_name: str = ""
    installed_version: str = ""
    login: str = ""  # mirrored for UI convenience; password never stored here
    update_asset_name: str = ""
    update_asset_pattern: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "github_repo": self.github_repo,
            "enabled": self.enabled,
            "module_id": self.module_id,
            "display_name": self.display_name,
            "installed_version": self.installed_version,
            "login": self.login,
            "update_asset_name": self.update_asset_name,
            "update_asset_pattern": self.update_asset_pattern,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceModuleConfig:
        update = data.get("update") if isinstance(data.get("update"), dict) else {}
        return cls(
            github_repo=str(data.get("github_repo") or ""),
            enabled=bool(data.get("enabled", False)),
            module_id=str(data.get("module_id") or ""),
            display_name=str(data.get("display_name") or ""),
            installed_version=str(data.get("installed_version") or ""),
            login=str(data.get("login") or ""),
            update_asset_name=str(
                data.get("update_asset_name") or update.get("asset_name") or ""
            ),
            update_asset_pattern=str(
                data.get("update_asset_pattern") or update.get("asset_pattern") or ""
            ),
        )


def parse_source_module_configs(raw: Any) -> list[SourceModuleConfig]:
    modules: list[SourceModuleConfig] = []
    if not isinstance(raw, list):
        return modules
    for item in raw:
        if isinstance(item, dict):
            modules.append(SourceModuleConfig.from_dict(item))
        elif isinstance(item, SourceModuleConfig):
            modules.append(item)
    return modules


@dataclass
class Settings:
    work_dir: str = "Working directory"
    template_name: str = ".template"
    archive_name: str = ".archive"
    highlight_warnings: bool = True
    warning_color: str = "#ff0000"
    warning_lead_days: int = 1
    create_notes_file: bool = False
    create_task_folder: bool = True
    autonumber_on_create: bool = False
    show_priority_colors: bool = True
    keep_priority_on_source_refresh: bool = False
    debug_logging: bool = False
    theme_mode: str = THEME_SYSTEM
    event_sound_enabled: bool = True
    event_sound_path: str = ""
    event_os_notification: bool = True
    event_snooze_minutes: int = DEFAULT_SNOOZE_MINUTES
    check_updates_on_startup: bool = True
    check_module_updates_on_startup: bool = True
    calendar_view: str = CALENDAR_VIEW_COMPACT
    calendar_week_splitter: list[int] = field(default_factory=list)
    calendar_compact_splitter: list[int] = field(default_factory=list)
    calendar_day_pane_open: bool = False
    image_preview_width: int = DEFAULT_IMAGE_PREVIEW_WIDTH
    show_in_tray: bool = True
    colors: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_COLORS))
    hotkeys: dict[str, str] = field(default_factory=default_hotkeys_copy)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["hotkeys"] = normalize_hotkeys(self.hotkeys)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Settings:
        defaults = cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        merged = defaults.to_dict()
        for key, value in data.items():
            if key in known:
                merged[key] = value
        if merged.get("theme_mode") not in THEME_MODES:
            merged["theme_mode"] = THEME_SYSTEM
        raw_hotkeys = merged.get("hotkeys")
        merged["hotkeys"] = normalize_hotkeys(
            raw_hotkeys if isinstance(raw_hotkeys, dict) else None
        )
        merged["event_sound_enabled"] = bool(merged.get("event_sound_enabled", True))
        merged["event_sound_path"] = parse_event_sound_path(
            merged.get("event_sound_path")
        )
        merged["event_os_notification"] = bool(merged.get("event_os_notification", True))
        merged["event_snooze_minutes"] = parse_snooze_minutes(
            merged.get("event_snooze_minutes")
        )
        merged["check_updates_on_startup"] = bool(
            merged.get("check_updates_on_startup", True)
        )
        merged["check_module_updates_on_startup"] = bool(
            merged.get("check_module_updates_on_startup", True)
        )
        merged["calendar_view"] = parse_calendar_view(merged.get("calendar_view"))
        merged["calendar_week_splitter"] = parse_splitter_sizes(
            merged.get("calendar_week_splitter")
        )
        merged["calendar_compact_splitter"] = parse_splitter_sizes(
            merged.get("calendar_compact_splitter")
        )
        merged["calendar_day_pane_open"] = bool(
            merged.get("calendar_day_pane_open", False)
        )
        merged["image_preview_width"] = parse_image_preview_width(
            merged.get("image_preview_width")
        )
        merged["show_in_tray"] = bool(merged.get("show_in_tray", True))
        merged["keep_priority_on_source_refresh"] = bool(
            merged.get("keep_priority_on_source_refresh", False)
        )
        return cls(**merged)


class SettingsStore:
    """Load/save settings.json at a given path (default: ./settings.json)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("settings.json")
        # One-shot migration from legacy settings.json source_modules list.
        self.pending_source_module_migration: list[SourceModuleConfig] = []

    def load(self) -> Settings:
        if not self.path.is_file():
            settings = Settings.from_dict({})
            self.pending_source_module_migration = []
            self.save(settings)
            self._ensure_work_dir(settings)
            return settings

        with self.path.open(encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict):
            raw = {}
        self.pending_source_module_migration = parse_source_module_configs(
            raw.pop("source_modules", None)
        )
        settings = Settings.from_dict(raw)
        # Normalize: drop unknown keys / fill missing by rewriting (no source_modules)
        self.save(settings)
        self._ensure_work_dir(settings)
        return settings

    def save(self, settings: Settings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(settings.to_dict(), fh, ensure_ascii=False, indent=2)

    @staticmethod
    def _ensure_work_dir(settings: Settings) -> None:
        path = resolve_work_dir(settings.work_dir)
        if not path.is_dir():
            path.mkdir(parents=True, exist_ok=True)
