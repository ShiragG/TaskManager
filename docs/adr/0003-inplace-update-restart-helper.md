# In-place update via `.new` and apply-on-exit helper

Frozen builds cannot reliably overwrite the running executable. We download the new GitHub asset next to the current one as `TaskManager[.exe].new`, show a banner with **«Установить и закрыть»**, then launch a short-lived helper (`.sh` / `.bat`) that waits for our PID, pauses briefly for file unlock, retries the replace, backs up to `.old`, replaces the binary, and `chmod`s on Unix. That helper does **not** start the new process: the downloaded file is still a onefile bootstrap (`_MEI` / `libpython` on Linux, analogous failure on Windows), so auto-relaunch right after self-replace is unreliable. The user starts the updated exe once; the bootstrap then unpacks onedir and relaunches (ADR 0016). The helper writes `taskmanager_update.log` beside the app for diagnosis. No OS message boxes (`msg` / `zenity`).

**Windows launch:** the helper must be started as `cmd.exe /c taskmanager_apply_update.bat` (not `Popen([bat])`), with **only** `CREATE_NEW_CONSOLE` so the script survives parent exit. Do **not** combine `DETACHED_PROCESS` with `CREATE_NEW_CONSOLE` (WinError 87). Use `chcp 65001` and avoid redirecting `move`/`del` stdout into the log (OEM mojibake). After a successful replace, log that the user should start the app manually — do not `start` the binary.

**Linux launch:** `/bin/sh` helper with `start_new_session` for the helper itself, mv retries on busy files, `chmod +x` after replace. Do **not** `setsid`/`nohup` the new binary from this helper.

Relaunch remains forbidden for this `.new` helper. It is allowed only after the bootstrap has unpacked onedir beside the exe (ADR 0016). Do not change the helper that old clients already ship.

## Fallback (reserved)

If the replace helper still fails on AV-locked / stubborn executables after the hardened A path, escalate to **B**: ship a small separate `updater` binary next to the app that performs the replace. Full installers (NSIS/Inno) stay out of the GitHub asset — a silent installer in `.new` would make the next start an installer, not the app.

**Status:** accepted
