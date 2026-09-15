# GitHub asset is a bootstrap that unpacks onedir

The published asset names stay `TaskManager` (Linux) and `TaskManager.exe` (Windows) so already-installed clients keep downloading the same file into `.new`. That file is no longer a GUI onefile. It is a console onefile **bootstrap** whose payload is a zip of the PyInstaller onedir (`TaskManager[.exe]` loader + `_internal`). Zip or NSIS/Inno as the asset would break those clients or turn the next start into an installer.

On first launch after the existing `.new` helper has swapped the file, the bootstrap unpacks the onedir **beside** the exe (not into `%TEMP%`/`_MEI` on every start). It must not overwrite `settings.json`, `taskmanager.db`, or `modules/`. The running bootstrap cannot replace itself: it writes the onedir loader to a temporary name, a short-lived helper waits for the bootstrap PID, moves the loader onto `TaskManager[.exe]`, and **relaunches with the same argv** (GUI or CLI). After that the exe is a normal onedir (`console=True` + `_internal`); CLI no longer pays onefile extract.

The apply-on-exit helper for `.new` is unchanged and still does not relaunch — the downloaded bytes are a onefile bootstrap (`_MEI`). Relaunch is allowed only for this onedir step. An already-installed onefile only needs the old helper; it does not need a new helper baked into that old build.

**Status:** accepted
