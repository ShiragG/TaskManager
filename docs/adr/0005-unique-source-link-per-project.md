# Unique source link per Project

Each Project may have at most one Task linked to a given Source item (`source_module_id` + `external_id`). Enforced with a partial UNIQUE index on `tasks` so Import UI “already imported” marks and create paths stay consistent under concurrency and older DBs. Soft UI-only checks were rejected: they do not stop duplicate inserts from other entry points.

**Status:** accepted

## Migration of existing duplicates

Before creating the index, rows that share `(directory_id, source_module_id, external_id)` (both source columns non-NULL) are deduped: the row with the minimum `id` keeps the original `external_id`; others are renamed to `{original}_Дубль_{8hex}` (sha256 of the task id, with retry on clash). Links are not cleared; Refresh-from-source on the canon Task keeps the real external id. Hard-deleting duplicate Tasks is out of scope.

## Consequences

- `create_task` maps unique-source violations to a clear `ServiceError`.
- Import may mark and disable already-imported rows and block the single-path open for those ids.
- Duplicate Tasks remain in the Project with a renamed `external_id` suffix rather than losing provenance.
