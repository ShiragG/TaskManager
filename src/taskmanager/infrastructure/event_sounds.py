"""Event ping sound: scan system folders and resolve a stored file path."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any, Sequence

from taskmanager.infrastructure.paths import app_dir


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
SETTINGS_SOUND_SENTINEL = "__settings_sound__"
SOUNDS_DIR_NAME = "sounds"


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
    file_path = os.fspath(path) if not isinstance(path, str) else path
    name = os.path.basename(file_path) or file_path
    if os.path.isfile(file_path):
        return name
    return f"{name} ({MISSING_FILE_MARK})"


def app_sounds_dir(*, base: Path | None = None) -> Path:
    return (base if base is not None else app_dir()) / SOUNDS_DIR_NAME


def copy_custom_sound(
    source: str | Path, *, dest_dir: Path | str | None = None
) -> Path:
    """Copy ``source`` into the app sounds folder. The original file is kept."""
    src_s = os.fspath(source) if not isinstance(source, str) else source
    raw_dest = dest_dir if dest_dir is not None else app_sounds_dir()
    target_s = raw_dest if isinstance(raw_dest, str) else os.fspath(raw_dest)
    os.makedirs(target_s, exist_ok=True)
    try:
        src_resolved = os.path.realpath(src_s)
        dest_resolved = os.path.realpath(target_s)
    except OSError:
        src_resolved = src_s
        dest_resolved = target_s
    if os.path.dirname(src_resolved) == dest_resolved:
        return Path(src_resolved)
    name = os.path.basename(src_s)
    stem, suffix = os.path.splitext(name)
    dest_s = os.path.join(target_s, name)
    n = 2
    while os.path.exists(dest_s):
        dest_s = os.path.join(target_s, f"{stem}_{n}{suffix}")
        n += 1
    shutil.copy2(src_resolved, dest_s)
    return Path(os.path.realpath(dest_s))


def event_ping_path(
    sound_path: str | None,
    settings_path: str,
    *,
    enabled: bool,
) -> str:
    """Path to play for an Event ping. Empty means silence."""
    if not enabled:
        return ""
    chosen = (sound_path or "").strip()
    return chosen or (settings_path or "").strip()
