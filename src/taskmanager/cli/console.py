from __future__ import annotations

import ctypes
import sys

# DWORD(-1): attach to the console of this process's parent.
ATTACH_PARENT_PROCESS = 0xFFFFFFFF


def attach_parent_console() -> None:
    """Attach CLI stdout/stderr to the parent Windows console.

    Frozen builds use the Windows subsystem (``console=False``) so a
    double-click never flashes a console. CLI still needs the terminal that
    launched us: ``AttachConsole`` plus reopen onto ``CONOUT$``. If there is
    no parent console, do nothing — never ``AllocConsole``. No-op off Windows.
    """
    if sys.platform != "win32":
        return
    kernel32 = _windows_kernel32()
    if not kernel32.AttachConsole(ATTACH_PARENT_PROCESS):
        return
    sys.stdout = _console_text_stream("CONOUT$")
    sys.stderr = _console_text_stream("CONOUT$")


def _console_text_stream(name: str):
    return open(name, "w", encoding="utf-8", errors="replace")


def _windows_kernel32() -> object:
    kernel32 = ctypes.windll.kernel32
    kernel32.AttachConsole.restype = ctypes.c_bool
    kernel32.AttachConsole.argtypes = [ctypes.c_uint]
    return kernel32
