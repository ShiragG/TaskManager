# In-place update via `.new` and restart helper (PyInstaller onefile)

Frozen builds cannot reliably overwrite the running executable. We download the new binary next to the current one as `TaskManager[.exe].new`, show a restart banner, then launch a short-lived helper (`.sh` / `.bat`) that waits for our PID, backs up to `.old`, replaces the binary, `chmod`s on Unix, starts the new process, and cleans up. Dev (non-frozen) downloads or prompts for manual replace without apply. Alternatives considered: Save As + manual swap (error-prone, no `chmod` on Linux) and switching to onedir/installer (out of scope for this release).

**Status:** accepted
