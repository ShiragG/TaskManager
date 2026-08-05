from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from taskmanager.infrastructure.paths import resolve_work_dir


DEFAULT_COLORS = {
    "Белый": "#ffffff",
    "Красный": "#ff0000",
    "Зелёный": "#99ff66",
    "Жёлтый": "#ffff00",
}

BASE_COLOR_NAMES = frozenset(DEFAULT_COLORS.keys())


@dataclass
class Settings:
    work_dir: str = "Working directory"
    template_name: str = ".template"
    archive_name: str = ".archive"
    highlight_warnings: bool = True
    warning_color: str = "#8B0000"
    warning_lead_days: int = 1
    create_notes_file: bool = True
    colors: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_COLORS))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Settings:
        defaults = cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        merged = defaults.to_dict()
        for key, value in data.items():
            if key in known:
                merged[key] = value
        return cls(**merged)


class SettingsStore:
    """Load/save settings.json at a given path (default: ./settings.json)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("settings.json")

    def load(self) -> Settings:
        if not self.path.is_file():
            settings = Settings()
            self.save(settings)
            self._ensure_work_dir(settings)
            return settings

        with self.path.open(encoding="utf-8") as fh:
            raw = json.load(fh)
        settings = Settings.from_dict(raw if isinstance(raw, dict) else {})
        # Normalize: drop unknown keys / fill missing by rewriting
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
