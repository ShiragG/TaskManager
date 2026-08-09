from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

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
    create_notes_file: bool = True
    create_task_folder: bool = True
    show_priority_colors: bool = True
    debug_logging: bool = False
    theme_mode: str = THEME_SYSTEM
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
        return cls(**merged)


class SettingsStore:
    """Load/save settings.json at a given path (default: ./settings.json)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("settings.json")
        # One-shot migration from legacy settings.json source_modules list.
        self.pending_source_module_migration: list[SourceModuleConfig] = []

    def load(self) -> Settings:
        if not self.path.is_file():
            settings = Settings()
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
