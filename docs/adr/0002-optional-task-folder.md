# Optional task folder (`has_folder`)

A task is primarily a SQLite record; the on-disk folder is optional. We store an explicit `has_folder` flag (not inferred only from disk) so missing folders can be distinguished from intentional DB-only tasks, and so archive/restore/open/rename can branch without treating every absent path as corruption. Alternatives considered: always requiring a folder (blocks lightweight requests), and inferring presence solely from the filesystem (ambiguous after deletes or moves outside the app).

**Status:** accepted

## Consequences

- Creation respects `create_task_folder`; Notes/template apply only when a folder is created.
- Archive moves the folder only when `has_folder` is true; otherwise only status/`archive_month` change.
- Startup warns for `has_folder` tasks whose folders are missing, with recreate or clear-flag actions.
