"""Event ping sound: scan system folders and resolve a stored file path."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Sequence


SOUND_EXTENSIONS = frozenset({".wav", ".ogg", ".oga", ".flac"})
PREFERRED_SOUND_NAMES = (
    "ding",
    "bell",
    "message",
    "notify",
    "complete",
    "dialog-information",
)
MISSING_FILE_MARK = "нет файла"
CUSTOM_SOUND_SENTINEL = "__custom_sound__"


def system_sound_roots() -> list[Path]:
    roots: list[Path] = []
    if sys.platform == "win32":
        windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
        roots.append(windir / "Media")
        return _unique_existing_dirs(roots)

    roots.append(Path("/usr/share/sounds"))
    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        roots.append(Path(data_home) / "sounds")
    else:
        roots.append(Path.home() / ".local/share/sounds")
    xdg_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    for raw in xdg_dirs.split(":"):
        if raw:
            roots.append(Path(raw) / "sounds")
    return _unique_existing_dirs(roots)


def _unique_existing_dirs(roots: Sequence[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for root in roots:
        try:
            resolved = root.resolve()
        except OSError:
            continue
        if not resolved.is_dir():
            continue
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        result.append(resolved)
    return result


def list_system_sound_files(*, roots: Sequence[Path] | None = None) -> list[Path]:
    search = list(roots) if roots is not None else system_sound_roots()
    found: list[Path] = []
    seen: set[str] = set()
    for root in search:
        if not root.is_dir():
            continue
        try:
            children = root.rglob("*")
        except OSError:
            continue
        for path in children:
            if path.suffix.lower() not in SOUND_EXTENSIONS:
                continue
            try:
                if not path.is_file():
                    continue
                key = str(path.resolve())
            except OSError:
                continue
            if key in seen:
                continue
            seen.add(key)
            found.append(path)
    found.sort(key=lambda item: item.name.casefold())
    return found


def first_preferred_sound_path(
    candidates: Sequence[Path] | None = None,
) -> str:
    files = list(candidates) if candidates is not None else list_system_sound_files()
    named = [(path, path.stem.casefold()) for path in files]
    for name in PREFERRED_SOUND_NAMES:
        needle = name.casefold()
        for path, stem in named:
            if needle in stem:
                return str(path)
    return ""


def parse_event_sound_path(
    value: Any,
    *,
    candidates: Sequence[Path] | None = None,
) -> str:
    if isinstance(value, str):
        path = value.strip()
    elif value is None:
        path = ""
    else:
        try:
            path = str(value).strip()
        except Exception:
            path = ""
    if path:
        return path
    return first_preferred_sound_path(candidates)


def sound_choice_label(path: str | Path) -> str:
    file_path = Path(path)
    name = file_path.name or str(path)
    if file_path.is_file():
        return name
    return f"{name} ({MISSING_FILE_MARK})"
