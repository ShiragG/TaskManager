# In-process Source modules as separate repositories

TaskManager loads optional Source modules as pure-Python zip plugins from `app_dir()/modules/` via importlib. Each external system (first: Razr at razr.pkzdrav.ru) lives in its **own repository** that publishes a zip on GitHub Releases; the host defines a `Protocol` plus `api_version` checks and never depends on a shared `taskmanager-source-api` package. Rejected: putting every source client inside TaskManager (couples release cycles), a TaskManager backend proxy, an out-of-process exe sidecar, and background sync for v1.

**Status:** accepted

## Registry and catalogs

- Module registry lives in SQLite (`source_modules`); credentials remain in `source_credentials`. Legacy `settings.json` `source_modules` lists are migrated once into SQLite and dropped from settings.
- The host stores no Razr URLs, status ids, or priority maps; blank add-module row accepts a GitHub URL only. Module-specific defaults (e.g. Razr `isMy`, default status filters) belong in the module / `plugin.json`.
- Status and priority catalogs (`list_statuses`, `list_priorities`) are fetched once per session (startup, after install/update/reload, or credential change) and cached for Import. On catalog failure the UI shows an error and does not call `list_items`.

## Agent note (not host code)

Sibling checkout for the first module: `/home/shirag/Projects/taskmanager-source-razr/`. Do not hardcode that path in the application.

## Consequences

- No modules installed or all disabled → locally created Tasks behave as today; Import / Refresh from source are unavailable.
- Module code must stay pure-Python (PyInstaller onefile host cannot load native extensions from the zip).
- Contract drift is managed by semver `api_version` in `plugin.json`, not by importing host types into the module.
- First module repository: `/home/shirag/Projects/taskmanager-source-razr/`.
