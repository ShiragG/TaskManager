# In-place update via `.new` and restart helper (PyInstaller onefile)

Frozen builds cannot reliably overwrite the running executable. We download the new binary next to the current one as `TaskManager[.exe].new`, show a restart banner, then launch a short-lived helper (`.sh` / `.bat`) that waits for our PID, pauses briefly for file unlock, retries the replace, backs up to `.old`, replaces the binary, `chmod`s on Unix, starts the new process detached, verifies it is alive, and cleans up. The helper writes `taskmanager_update.log` beside the app for diagnosis; on Unix, the new binary's stderr goes to `taskmanager_update.crash.log` so a launch crash is not swallowed.

**Windows launch:** the helper must be started as `cmd.exe /c taskmanager_apply_update.bat` (not `Popen([bat])`), with **only** `CREATE_NEW_CONSOLE` so the script survives parent exit. Do **not** combine `DETACHED_PROCESS` with `CREATE_NEW_CONSOLE` (WinError 87). After replace, start with `start "" /D "<appdir>" "%TARGET%"`, then `tasklist` to log relaunch OK/FAIL. Use `chcp 65001` and avoid redirecting `move`/`del` stdout into the log (OEM mojibake).

**Linux launch:** `/bin/sh` helper with `start_new_session`, `setsid`/`nohup` for the new binary (stderr → `.crash.log`), `sleep` + `kill -0` to log relaunch OK/FAIL, and mv retries on busy files.

## Fallback (reserved)

If the onefile helper still fails on AV-locked / stubborn executables after the hardened A path, escalate to **B**: ship a small separate `updater` binary next to the app that performs the replace (more reliable than a shell script, still without switching distribute format). Onedir installers (C) and full installers (D) remain out of scope unless we change packaging.

Alternatives considered: Save As + manual swap (error-prone, no `chmod` on Linux) and switching to onedir/installer (out of scope for this release).

**Status:** accepted
