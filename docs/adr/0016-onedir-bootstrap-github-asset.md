# GitHub asset is a bootstrap that unpacks onedir

The published asset names stay `TaskManager` (Linux) and `TaskManager.exe` (Windows) so already-installed clients keep downloading the same file into `.new`. That file is no longer a GUI onefile. It is a console onefile **bootstrap** whose payload is a zip of the PyInstaller onedir (`TaskManager[.exe]` loader + `data/`). Zip or NSIS/Inno as the asset would break those clients or turn the next start into an installer.

`TaskManager.spec` COLLECT writes to `build/onedir-collect/` (not `dist/`). After `package_github_asset.py`, `dist/` holds only the GitHub asset.

On first launch after the existing `.new` helper has swapped the file, the bootstrap hides an exclusive Windows console (double-click) then unpacks the onedir **beside** the exe (not into `%TEMP%`/`_MEI` on every start). Runtime files go in `data/` next to the exe; `settings.json`, `taskmanager.db`, and `modules/` stay at the install root and must not be overwritten. After a successful extract, leftover `_internal` from older runs is removed. The running bootstrap cannot replace itself: it writes the onedir loader to a temporary name, a short-lived helper waits for the bootstrap PID, moves the loader onto `TaskManager[.exe]`, and **relaunches with the same argv** (GUI or CLI). The Windows bootstrap helper uses `CREATE_NO_WINDOW` (not `CREATE_NEW_CONSOLE`, which would flash an empty cmd). After that the exe is a normal onedir (`console=True` + `data/`); CLI no longer pays onefile extract.

The apply-on-exit helper for `.new` is unchanged and still does not relaunch — the downloaded bytes are a onefile bootstrap (`_MEI`). Relaunch is allowed only for this onedir step. An already-installed onefile only needs the old helper; it does not need a new helper baked into that old build. Do not change that helper's `CREATE_NEW_CONSOLE` (ADR 0003).

**Status:** accepted
