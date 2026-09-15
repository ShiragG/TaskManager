# Windows: оконная подсистема и AttachConsole для CLI

Двойной клик по exe должен открывать GUI без окна консоли. Консольная сборка (`console=True`) даёт вспышку: Windows рисует консоль до запуска Python, а `hide_console` только прячет уже видимое окно. Вспышка неприемлема. Сборка — оконная (`console=False`, bootloader `runw.exe`).

CLI из открытого терминала должен печатать в тот же сеанс: при `len(argv) > 1` процесс делает `AttachConsole` к родителю и открывает stdout/stderr на `CONOUT$`, затем печатает. Если родителя нет (двойной клик с аргументами) — не `AllocConsole`, окна консоли нет, как раньше. GUI консоль не трогает и не создаёт.

Pipe (`|`) и перенаправление (`>`) на Windows CLI не обещаем: `AttachConsole` пишет на экран консоли, не в pipe. Печать в уже открытый PowerShell и `--help` — да. Linux: `console=False` stdout из терминала не отрезает.

**Status:** accepted

## Considered Options

- **`console=True` + скрытие эксклюзивной консоли** — полный контракт «как Linux» (pipe, redirect, синхронный захват терминала), но вспышка окна при двойном клике. Отклонено.
- **Два бинаря: GUI + CLI** — максимально чисто, но удваивает артефакты дистрибутива. Единый бинарь выбран из-за простоты выпуска.
- **Оконная сборка + `AttachConsole` (выбрано)** — нет вспышки; CLI печатает в открытый PowerShell. Цена: pipe/`>` на Windows не обещаем.

## Consequences

- `console=False` в [`TaskManager.spec`](../../TaskManager.spec) и в bootstrap spec (`render_bootstrap_spec`). Это не то же самое, что вручную вызывать `pyinstaller --windowed … __main__.py`: флаги в argv побеждают spec и ломают onedir COLLECT. См. README.
- CLI вызывает `attach_parent_console()` до печати. GUI-ветка консоль не трогает.
- Helper после распаковки onedir: GUI — `CREATE_NO_WINDOW`, relaunch без `start` (иначе новая консоль). CLI — helper наследует уже присоединённую консоль (без `CREATE_NO_WINDOW`), relaunch без `start`, чтобы дочерний onedir снова сделал `AttachConsole` к той же консоли.
- Helper `.new` не меняем ([ADR 0003](0003-inplace-update-restart-helper.md)).
