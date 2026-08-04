# TaskManager

Приложение для ведения заявок: каждая заявка — папка на диске и запись в SQLite, сгруппированные по директориям (вкладки).

Словарь терминов: [`CONTEXT.md`](CONTEXT.md). Архитектура: [`docs/adr/0001-layered-desktop-architecture.md`](docs/adr/0001-layered-desktop-architecture.md).

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
2. Создайте **директорию** (вкладка) — появится одноимённая папка в `work_dir`.
3. При необходимости положите шаблон в `{директория}/{template_name}` (по умолчанию `.template`).
4. Создайте **заявку** — папка с именем = **номер** заявки; при флаге «из шаблона» содержимое копируется из шаблона.
5. Ссылки на заявку хранятся в БД; ПКМ по строке → «Открыть ссылку».
6. **Архив** переносит папку в `{work_dir}/{archive_name}/{YYYY_MM}/` и ставит статус `archived`.

Метаданные (номер, описание, срок, цвет, ссылки) живут в SQLite рядом с исполняемым файлом. Имя папки на диске совпадает с номером: при смене номера папка переименовывается автоматически.

## Настройки (`settings.json`)

`settings.json` и `taskmanager.db` создаются **рядом с исполняемым файлом** (в режиме разработки — в текущем рабочем каталоге запуска).

| Ключ | Назначение |
|------|------------|
| `work_dir` | Корень рабочих папок |
| `template_name` | Имя папки-шаблона в директории |
| `archive_name` | Имя корня архива |
| `highlight_warnings` | Подсветка сроков (просрочка и ближайшие дни) |
| `warning_lead_days` | За сколько дней до срока начинать подсветку (по умолчанию 1) |
| `warning_color` | Цвет подсветки |
| `colors` | Палитра цветов строк |

Версия приложения и контакты — в настройках («О приложении»).

## Поиск и правки

- Ctrl+F / поле поиска — фильтр по номеру и описанию на текущей вкладке.
- Чекбокс **Скрытые** — только скрытые заявки; без него — только обычные.
- Палитра цветов над таблицей — покрасить выделенную заявку; «+» добавляет цвет; ПКМ по кастомному swatch удаляет его из настроек.
- Двойной клик — редактирование заявки (при смене номера папка на диске переименовывается).
- ПКМ по строке — изменить, открыть папку, архив, удалить, ссылки.
- ПКМ по вкладке директории — изменить, открыть папку, удалить.
- F5 — обновить текущую вкладку.
- Таблица: колонки **Номер → Срок → Описание**; цвет заявки заливает строку; клик по заголовку сортирует (по умолчанию номер по возрастанию).

## Тесты

```bash
uv run pytest
```

## Сборка (PyInstaller)

Сборку выполняйте **на целевой ОС** (кросс-сборка Win↔Linux не поддерживается). Артефакт: `TaskManager` на Linux, `TaskManager.exe` на Windows. `settings.json` и `taskmanager.db` создаются рядом с exe.

```bash
uv sync --all-groups
```

**Linux:**

```bash
uv run pyinstaller --noconfirm --onefile --windowed \
  --name TaskManager \
  --icon src/taskmanager/resources/app_icon.ico \
  --add-data "src/taskmanager/ui/styles/app.qss:taskmanager/ui/styles" \
  --add-data "src/taskmanager/resources/app_icon.png:taskmanager/resources" \
  --add-data "src/taskmanager/resources/app_icon.ico:taskmanager/resources" \
  src/taskmanager/__main__.py
```

**Windows** (разделитель путей в `--add-data` — `;`):

```bash
uv run pyinstaller --noconfirm --onefile --windowed --name TaskManager --icon src/taskmanager/resources/app_icon.ico --add-data "src/taskmanager/ui/styles/app.qss;taskmanager/ui/styles" --add-data "src/taskmanager/resources/app_icon.png;taskmanager/resources" --add-data "src/taskmanager/resources/app_icon.ico;taskmanager/resources" src/taskmanager/__main__.py
```

Готовый бинарник появится в `dist/`. Для публикации на GitHub Releases прикладывайте assets с именами **`TaskManager`** (Linux) и **`TaskManager.exe`** (Windows) — см. [`GITHUB_RELEASES_SETUP.md`](GITHUB_RELEASES_SETUP.md). Проверка обновлений в настройках скачивает выбранный файл через «Сохранить как…» без самозамены exe.

## Что не входит в v1

Связи между заявками, поиск по содержимому файлов, массовый архив директории, миграция старых `.taskData.json`, Oracle, хранилище, сторонние проводники, тёмная тема, кросс-сборка Win↔Linux.
