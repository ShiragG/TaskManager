from __future__ import annotations

import ctypes
import sys

SW_HIDE = 0


def hide_console_if_only_ours() -> None:
    """Hide the Windows console when it belongs to this process alone.

    The frozen binary is a console-subsystem app so that CLI output behaves
    exactly as it does on Linux: pipes and redirection work, exit codes
    propagate, and a terminal blocks until the command finishes. A console
    window is only welcome in that terminal case. When the OS created a fresh
    console for us — a double-click or a launch from Explorer — the window is
    exclusively ours and would be noise for the GUI, so hide it. When we share
    a console with a terminal (cmd, PowerShell), somebody else owns the window
    and we must not touch it. No-op when not on Windows.
    """
    if sys.platform != "win32":
        return
    kernel32 = _windows_kernel32()
    console_window = kernel32.GetConsoleWindow()
    if not console_window:
        return
    process_list = (ctypes.c_uint * 4)()
    count = kernel32.GetConsoleProcessList(process_list, 4)
    if count <= 1:
        _windows_user32().ShowWindow(console_window, SW_HIDE)


def _windows_kernel32() -> object:
    kernel32 = ctypes.windll.kernel32
    kernel32.GetConsoleWindow.restype = ctypes.c_void_p  # HWND is pointer-sized
    kernel32.GetConsoleProcessList.restype = ctypes.c_uint
    kernel32.GetConsoleProcessList.argtypes = [
        ctypes.POINTER(ctypes.c_uint),
        ctypes.c_uint,
    ]
    return kernel32


def _windows_user32() -> object:
    user32 = ctypes.windll.user32
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    return user32