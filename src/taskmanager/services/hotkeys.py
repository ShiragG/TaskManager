"""Default shortcuts and validation for MainWindow actions."""

from __future__ import annotations

from copy import deepcopy

from PySide6.QtGui import QKeySequence

# action_id → default QKeySequence string
DEFAULT_HOTKEYS: dict[str, str] = {
    "focus_search": "Ctrl+F",
    "add_task": "Ctrl+N",
    "reload_current_tab": "F5",
}

HOTKEY_LABELS: dict[str, str] = {
    "focus_search": "Поиск",
    "add_task": "Новая задача",
    "reload_current_tab": "Обновить вкладку",
}

HOTKEY_ORDER: tuple[str, ...] = (
    "focus_search",
    "add_task",
    "reload_current_tab",
)


def normalize_hotkeys(raw: dict[str, str] | None) -> dict[str, str]:
    """Merge user values with defaults; drop unknown action ids."""
    result = dict(DEFAULT_HOTKEYS)
    if not raw:
        return result
    for key, value in raw.items():
        if key in result and isinstance(value, str) and value.strip():
            result[key] = value.strip()
    return result


def sequence_key(text: str) -> str:
    """Canonical comparable form of a key sequence (empty if invalid)."""
    seq = QKeySequence(text.strip())
    if seq.isEmpty():
        return ""
    return seq.toString(QKeySequence.SequenceFormat.PortableText)


def validate_hotkeys(hotkeys: dict[str, str]) -> str | None:
    """
    Return an error message, or None if valid.

    Rules: every known action has a non-empty sequence; no duplicates.
    Empty / missing values are errors (do not silently fall back to defaults).
    """
    seen: dict[str, str] = {}
    for action_id in HOTKEY_ORDER:
        text = (hotkeys.get(action_id) or "").strip()
        label = HOTKEY_LABELS.get(action_id, action_id)
        if not text:
            return f"Укажите сочетание для «{label}»"
        key = sequence_key(text)
        if not key:
            return f"Некорректное сочетание для «{label}»: {text}"
        if key in seen:
            other = HOTKEY_LABELS.get(seen[key], seen[key])
            return f"Конфликт: «{label}» и «{other}» используют {key}"
        seen[key] = action_id
    return None


def hotkeys_to_store(hotkeys: dict[str, str]) -> dict[str, str]:
    """Portable strings for settings.json (assumes already validated)."""
    out: dict[str, str] = {}
    for action_id in HOTKEY_ORDER:
        text = (hotkeys.get(action_id) or "").strip()
        key = sequence_key(text)
        out[action_id] = key or DEFAULT_HOTKEYS[action_id]
    return out


def default_hotkeys_copy() -> dict[str, str]:
    return deepcopy(DEFAULT_HOTKEYS)
