from __future__ import annotations

import sys
from typing import Protocol


ATTACH_PARENT_PROCESS = 0xFFFFFFFF  # DWORD -1


class _Kernel32(Protocol):
    def AttachConsole(self, dw_process_id: int) -> int: ...


def attach_parent_console() -> None:
    """Make stdout/stderr visible for a frozen windowed Windows binary.

    ``TaskManager.spec`` keeps ``console=False`` so a double-click still has no
    extra console. When launched from a terminal with CLI arguments, attach the
    parent console and reopen streams before any print. If there is no parent
    console, do not allocate a new one — stdout goes nowhere. No-op when not
    frozen or not on Windows.
    """
    if not getattr(sys, "frozen", False):
        return
    if sys.platform != "win32":
        return
    kernel32 = _windows_kernel32()
    if not kernel32.AttachConsole(ATTACH_PARENT_PROCESS):
        return
    _reopen_stdio()


def _windows_kernel32() -> _Kernel32:
    import ctypes

    return ctypes.windll.kernel32  # type: ignore[no-any-return]


def _reopen_stdio() -> None:
    sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")
    sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")
