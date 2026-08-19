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

```bash
uv run python -m taskmanager
```

или

```bash
uv run taskmanager
```

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

Сборку выполняйте **на целевой ОС** (кросс-сборка Win↔Linux не поддерживается). Артефакт: `TaskManager` на Linux, `TaskManager.exe` на Windows.

```bash
uv sync --all-groups
```

**Linux:**

```bash
uv run pyinstaller --noconfirm --onefile --windowed \
  --name TaskManager \
  --icon src/taskmanager/resources/app_icon.ico \
  --add-data "src/taskmanager/ui/styles/app.qss:taskmanager/ui/styles" \
  --add-data "src/taskmanager/ui/styles/app_dark.qss:taskmanager/ui/styles" \
  --add-data "src/taskmanager/resources/app_icon.png:taskmanager/resources" \
  --add-data "src/taskmanager/resources/app_icon.ico:taskmanager/resources" \
  src/taskmanager/__main__.py
```

**Windows** (разделитель путей в `--add-data` — `;`):

```bash
uv run pyinstaller --noconfirm --onefile --windowed --name TaskManager --icon src/taskmanager/resources/app_icon.ico --add-data "src/taskmanager/ui/styles/app.qss;taskmanager/ui/styles" --add-data "src/taskmanager/ui/styles/app_dark.qss;taskmanager/ui/styles" --add-data "src/taskmanager/resources/app_icon.png;taskmanager/resources" --add-data "src/taskmanager/resources/app_icon.ico;taskmanager/resources" src/taskmanager/__main__.py
```

Готовый бинарник появится в `dist/`. Для публикации на GitHub Releases прикладывайте assets с именами **`TaskManager`** (Linux) и **`TaskManager.exe`** (Windows) — см. [`GITHUB_RELEASES_SETUP.md`](GITHUB_RELEASES_SETUP.md).

## Что не входит в v1

Связи между заявками, поиск по содержимому файлов, массовый архив проекта, миграция старых `.taskData.json`, Oracle, автоудаление пустых папок проектов, onedir/installer вместо onefile helper, кросс-сборка Win↔Linux.
