# In-place update via `.new` and restart helper (PyInstaller onefile)

Frozen builds cannot reliably overwrite the running executable. We download the new binary next to the current one as `TaskManager[.exe].new`, show a restart banner, then launch a short-lived helper (`.sh` / `.bat`) that waits for our PID, pauses briefly for file unlock, retries the replace, backs up to `.old`, replaces the binary, `chmod`s on Unix, starts the new process detached, and cleans up. The helper writes `taskmanager_update.log` beside the app for diagnosis. Dev (non-frozen) downloads or prompts for manual replace without apply.

**Windows launch:** the helper must be started as `cmd.exe /c taskmanager_apply_update.bat` (not `Popen([bat])`), with a new console / detached process group so the script survives parent exit.

**Linux launch:** `/bin/sh` helper with `start_new_session`, `setsid`/`nohup` for the new binary, and mv retries on busy files.

## Fallback (reserved)

If the onefile helper still fails on AV-locked / stubborn executables after the hardened A path, escalate to **B**: ship a small separate `updater` binary next to the app that performs the replace (more reliable than a shell script, still without switching distribute format). Onedir installers (C) and full installers (D) remain out of scope unless we change packaging.

Alternatives considered: Save As + manual swap (error-prone, no `chmod` on Linux) and switching to onedir/installer (out of scope for this release).

**Status:** accepted
