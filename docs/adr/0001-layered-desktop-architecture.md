# Layered desktop architecture

TaskManager is a desktop app with filesystem side effects and a Qt UI. We split it into `domain` (pure models), `services` (use cases), `infrastructure` (SQLite, filesystem, platform open), and `ui` (PySide6) so business rules stay testable without Qt and so Oracle/JSON/explorer concerns cannot leak back in. Alternatives considered: keeping the flat god-object (untestable, hard to cut features) and a ports-and-adapters grid with many interfaces (overkill for one SQLite adapter and one FS adapter).

**Status:** accepted

## Consequences

- UI talks only to services; services own transactions that touch DB + disk together.
- Domain has no Qt, sqlite3, or `pathlib` I/O — only value objects and invariants.
- Platform open (browser / file manager / default app) lives in infrastructure, not settings.
