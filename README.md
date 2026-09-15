# TaskManager

Приложение для ведения заявок: метаданные в SQLite, папка на диске опциональна; заявки группируются по **проектам** (вкладки).

Словарь терминов: [`CONTEXT.md`](CONTEXT.md). Архитектура: [`docs/adr/`](docs/adr/).

## Требования

- [uv](https://astral.sh/uv/)
- Python ≥ 3.13

## Установка

```bash
uv sync --all-groups
```

## Запуск

Без аргументов открывается графическое окно:

```bash
uv run python -m taskmanager
```

или

```bash
uv run taskmanager
```

Любой аргумент включает консольный режим: процесс выполняет команду и завершается (то же `settings.json` и `taskmanager.db`, что у GUI). Адрес заявки — **имя проекта** и **номер**. Живой Source item можно читать по id модуля и `external_id`, без проекта. `--help` всегда печатает текст argparse, даже вместе с `--json`. Полный help всех подкоманд: `--help-all` (`--json` на него не действует).

```bash
uv run taskmanager --help
uv run taskmanager --help-all
uv run taskmanager project list
uv run taskmanager project create --name Alpha
uv run taskmanager project rename --project Alpha --name Beta
uv run taskmanager project delete --project Beta
uv run taskmanager task list --project Alpha
uv run taskmanager task list --project Alpha --hidden
uv run taskmanager task list --project Alpha --archive
uv run taskmanager task search QUERY [--archive]
uv run taskmanager task create --project Alpha --description "Черновик"
uv run taskmanager task get --project Alpha --number 1
uv run taskmanager task update --project Alpha --number 1 --status in_progress
uv run taskmanager task comment set --project Alpha --number 1 --text "замена"
uv run taskmanager task comment append --project Alpha --number 1 --text "сдвиг срока"
uv run taskmanager task archive --project Alpha --number 1
uv run taskmanager task restore --project Alpha --number 1
uv run taskmanager task hide --project Alpha --number 1
uv run taskmanager task unhide --project Alpha --number 1
uv run taskmanager task delete --project Alpha --number 1
uv run taskmanager task folder --project Alpha --number 1
uv run taskmanager task folder ensure --project Alpha --number 1
uv run taskmanager task excel --project Alpha --output Alpha.xlsx
uv run taskmanager link list --project Alpha --number 1
uv run taskmanager link add --project Alpha --number 1 --name docs --target https://example.com
uv run taskmanager link remove --project Alpha --number 1 --name docs
uv run taskmanager source module list
uv run taskmanager task source --module ID --external-id X
uv run taskmanager task source --project Alpha --number 1
uv run taskmanager task source refresh --project Alpha --number 1
uv run taskmanager --json task list --project Alpha
```

`--help` и ключи JSON на английском. `list` печатает таблицу; `get` и `task source` — JSON. Глобальный `--json` переводит любую команду в JSON. Папка заявки необязательна: без неё `get` отдаёт `"folder": null`, путь создаёт `task folder ensure`. Удаление и архив выполняются сразу, без подтверждения. Если GUI уже открыт, CLI всё равно пишет в ту же SQLite; таблицу в окне обновляет F5.

## Рабочий цикл

1. В настройках укажите **рабочую директорию** (`work_dir`).
2. Создайте **проект** (вкладка) — папка на диске появится лениво при первой заявке с папкой или «Открыть папку».
3. При необходимости положите шаблон в `{проект}/{template_name}` (по умолчанию `.template`).
4. Создайте **заявку** — запись в БД; при включённой папке имя каталога = **номер**; при флаге «из шаблона» содержимое копируется из шаблона.
5. **Комментарий** — HTML-поле в БД (отдельно от Notes.txt).
6. Ссылки на заявку хранятся в БД; ПКМ по строке → «Открыть ссылку».
7. **Архив** ставит статус `archived` и переносит папку в `{work_dir}/{archive_name}/{YYYY_MM}/{project}/` *если папка есть*; режим «Архив» + «Вернуть» для просмотра и восстановления.

Метаданные (номер, описание, комментарий, срок, приоритет, цвет, `has_folder`, ссылки) живут в SQLite рядом с исполняемым файлом. Цвет «Без цвета» хранится как NULL; «Белый» — `#ffffff`. Приоритет — целое 0–10 (0 критично, 10 спокойно; по умолчанию 10), отдельно от цвета строки.

## Настройки (`settings.json`)

`settings.json`, `taskmanager.db` и `taskmanager.log` создаются **рядом с исполняемым файлом** (в режиме разработки — в текущем рабочем каталоге запуска).

| Ключ | Назначение |
|------|------------|
| `work_dir` | Корень рабочих папок |
| `template_name` | Имя папки-шаблона в проекте |
| `archive_name` | Имя корня архива |
| `theme_mode` | `light` / `dark` / `system` |
| `highlight_warnings` | Подсветка сроков (просрочка и ближайшие дни) |
| `warning_lead_days` | За сколько дней до срока начинать подсветку (по умолчанию 1) |
| `warning_color` | Цвет подсветки |
| `colors` | Палитра цветов строк («Белый» ≠ «Без цвета») |
| `create_task_folder` | Создавать папку заявки по умолчанию |
| `create_notes_file` | Создавать `Notes.txt` и ссылку «Заметки» при новой заявке с папкой (по умолчанию выкл.; уже сохранённый `true` не меняется) |
| `show_priority_colors` | Цвет фона ячейки приоритета по шкале 0→красный … 10→зелёный |
| `keep_priority_on_source_refresh` | Не изменять приоритет при обновлении из источника (по умолчанию выкл.) |
| `debug_logging` | Писать INFO/DEBUG действий в `taskmanager.log` |

Версия приложения и контакты — в настройках («О приложении»). Обновление (frozen): скачивание в `TaskManager[.exe].new` рядом с exe → баннер «Установить и закрыть» (после закрытия файл заменят — запустите приложение снова вручную) → helper ждёт PID и подменяет бинарник (`chmod` на Linux), без автозапуска. В dev — файл скачивается, замена вручную.

## Поиск и правки

- Ctrl+F / поле поиска — фильтр по номеру, описанию и комментарию на текущей вкладке.
- Чекбоксы **Скрытые** и **Архив** взаимоисключающие.
- Палитра: ∅ = без цвета; «Белый» и остальные swatch’и; «+» добавляет цвет; ПКМ по кастомному — удалить из настроек.
- Двойной клик — редактирование (описание/комментарий через «…»; `created_at` только для чтения).
- ПКМ по строке — изменить, открыть папку, архив/вернуть, удалить, ссылки.
- ПКМ по вкладке проекта — изменить, открыть папку, удалить.
- **Excel…** — экспорт выбранных проектов (`openpyxl`).
- F5 — обновить текущую вкладку.
- Таблица: **Приоритет → Номер → Срок → Описание → Комментарий**.

## Сборка (PyInstaller)

Сборку выполняйте **на целевой ОС** (кросс-сборка Win↔Linux не поддерживается). Один вход для Linux и Windows — `TaskManager.spec` (разделитель `--add-data` уже внутри spec, не в argv). Артефакт: `TaskManager` на Linux, `TaskManager.exe` на Windows.

```bash
uv sync --all-groups
uv run pyinstaller --noconfirm TaskManager.spec
```

**Не** добавляйте `--windowed` / `--noconsole` на Windows. Эти флаги ставят GUI-подсистему Windows: у процесса нет stdout, поэтому `.\TaskManager.exe --help` в PowerShell молчит. Это не баг CLI и не отличие cmd от PowerShell. На Linux `--windowed` PyInstaller игнорирует; копировать linux-команду с `--windowed` на Windows нельзя. Команды вида `pyinstaller … src/taskmanager/__main__.py` устарели: флаги в argv побеждают spec, даже если spec лежит рядом.

После смены флага консоли пересоберите `dist` на той же ОС. Проверка: `.\TaskManager.exe --help` (PowerShell) / `TaskManager.exe --help` (cmd) печатает Usage. GUI без аргументов: двойной клик прячет консоль; из терминала консоль остаётся (как на Linux). Подробности: [`docs/adr/0015-windows-console-subsystem.md`](docs/adr/0015-windows-console-subsystem.md).

Готовый бинарник появится в `dist/`. Для публикации на GitHub Releases прикладывайте assets с именами **`TaskManager`** (Linux) и **`TaskManager.exe`** (Windows) — см. [`GITHUB_RELEASES_SETUP.md`](GITHUB_RELEASES_SETUP.md).

## Что не входит в v1

Связи между заявками, поиск по содержимому файлов, массовый архив проекта, миграция старых `.taskData.json`, Oracle, автоудаление пустых папок проектов, onedir/installer вместо onefile helper, кросс-сборка Win↔Linux.
