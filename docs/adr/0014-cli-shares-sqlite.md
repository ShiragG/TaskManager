# CLI shares SQLite with the GUI and skips InstanceGuard

The GUI already enforces one window per app directory via `InstanceGuard` (lock file + local socket). A command-line mode that went through the same guard would either steal the lock, fail while the window is open, or need a second database. Operators need to create, inspect, and update Tasks while the desktop app may already be running, using the same `settings.json` and `taskmanager.db` next to the binary. The CLI therefore bypasses `InstanceGuard`, opens the same SQLite file, and exits when the command finishes. The open window does not refresh itself; F5 reloads the current tab.

**Status:** accepted

## Considered Options

- **Second database or a CLI-only profile** — splits Project/Task state; the GUI would not see CLI writes without a sync path we do not have.
- **Route CLI through InstanceGuard** — a second process cannot become primary; it would only raise the existing window (`notify_existing`) and could not run a command. Serializing every mutation through the GUI process would couple argparse to Qt slots and break headless use.
- **Share SQLite, skip the guard** — one source of truth; SQLite already serializes writers. The cost is a stale GUI until F5, which is the same reload the table already supports.

## Consequences

- `run()` sends `argv` with no extra arguments to the GUI (guard, `QApplication`, `MainWindow`, SourceHost, update checks). Any extra argument (`--help`, `project list`, unknown tokens) is CLI: no guard, no window, process exits `0` / `1` / `2`. SourceHost is constructed only for `source module *` and `task source *`.
- CLI uses the same `default_settings_path()` / `default_db_path()` as the GUI. Identity in the CLI contract is Project name + Task Number, never SQLite `id`.
- Headless Qt (`QT_QPA_PLATFORM=offscreen` when unset) is enough for `html_to_plain` (`QTextDocument`). Windows builds are windowed (`console=False`); CLI attaches to the parent console — see [ADR 0015](0015-windows-console-subsystem.md).
