# In-place update via `.new` and apply-on-exit helper (PyInstaller onefile)

Frozen builds cannot reliably overwrite the running executable. We download the new binary next to the current one as `TaskManager[.exe].new`, show a banner with **«Установить и закрыть»**, then launch a short-lived helper (`.sh` / `.bat`) that waits for our PID, pauses briefly for file unlock, retries the replace, backs up to `.old`, replaces the binary, and `chmod`s on Unix. The helper does **not** start the new process: PyInstaller onefile (`_MEI` / `libpython` on Linux, analogous failure on Windows) makes auto-relaunch right after self-replace unreliable. The user starts the updated exe manually. The helper writes `taskmanager_update.log` beside the app for diagnosis. No OS message boxes (`msg` / `zenity`).

**Windows launch:** the helper must be started as `cmd.exe /c taskmanager_apply_update.bat` (not `Popen([bat])`), with **only** `CREATE_NEW_CONSOLE` so the script survives parent exit. Do **not** combine `DETACHED_PROCESS` with `CREATE_NEW_CONSOLE` (WinError 87). Use `chcp 65001` and avoid redirecting `move`/`del` stdout into the log (OEM mojibake). After a successful replace, log that the user should start the app manually — do not `start` the binary.

**Linux launch:** `/bin/sh` helper with `start_new_session` for the helper itself, mv retries on busy files, `chmod +x` after replace. Do **not** `setsid`/`nohup` the new binary.

## Fallback (reserved)

If the onefile helper still fails on AV-locked / stubborn executables after the hardened A path, escalate to **B**: ship a small separate `updater` binary next to the app that performs the replace (more reliable than a shell script, still without switching distribute format). Onedir installers (C) and full installers (D) remain out of scope unless we change packaging.

Alternatives considered: auto-relaunch from the helper (rejected — `_MEI` / load failures), Save As + manual swap (error-prone, no `chmod` on Linux), and switching to onedir/installer (out of scope for this release).

**Status:** accepted
