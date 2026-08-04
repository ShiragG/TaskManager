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
4. Создайте **заявку** — папка `{номер}___{описание}`; при флаге «из шаблона» содержимое копируется из шаблона.
5. Ссылки на заявку хранятся в БД; ПКМ по строке → «Открыть ссылку».
6. **Архив** переносит папку в `{work_dir}/{archive_name}/{YYYY_MM}/` и ставит статус `archived`.

Метаданные (номер, описание, срок, цвет, ссылки) живут только в SQLite (каталог данных приложения). **Не переименовывайте папки заявок вручную** — имя папки фиксируется при создании.

## Настройки (`settings.json`)

Файл настроек и SQLite по умолчанию лежат в каталоге данных приложения (Linux: `~/.local/share/taskmanager/`, Windows: `%APPDATA%\taskmanager\`).

| Ключ | Назначение |
|------|------------|
| `work_dir` | Корень рабочих папок |
| `template_name` | Имя папки-шаблона в директории |
| `archive_name` | Имя корня архива |
| `highlight_warnings` | Подсветка просроченных сроков |
| `warning_color` | Цвет подсветки |
| `colors` | Палитра цветов строк |

Версия приложения и контакты — в настройках («О приложении»).

## Поиск и правки

- Ctrl+F / поле поиска — фильтр по номеру и описанию на текущей вкладке.
- Двойной клик — редактирование заявки (папка на диске не переименовывается).
- ПКМ по строке — изменить, открыть папку, архив, удалить, ссылки.
- ПКМ по вкладке директории — изменить, открыть папку, удалить.
- Таблица: колонки **Номер → Срок → Описание**; цвет заявки заливает строку; клик по заголовку сортирует (по умолчанию номер по возрастанию).

## Тесты

```bash
uv run pytest
```

## Сборка (PyInstaller)

Сборку выполняйте **на целевой ОС** (кросс-сборка Win↔Linux не поддерживается). Артефакт: `TaskManager` на Linux, `TaskManager.exe` на Windows. Данные (`settings.json`, SQLite) остаются в каталоге данных пользователя, не рядом с exe.

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
uv run pyinstaller --noconfirm --onefile --windowed \
  --name TaskManager \
  --icon src/taskmanager/resources/app_icon.ico \
  --add-data "src/taskmanager/ui/styles/app.qss;taskmanager/ui/styles" \
  --add-data "src/taskmanager/resources/app_icon.png;taskmanager/resources" \
  --add-data "src/taskmanager/resources/app_icon.ico;taskmanager/resources" \
  src/taskmanager/__main__.py
```

Готовый бинарник появится в `dist/`.

## Что не входит в v1

Связи между заявками, поиск по содержимому файлов, массовый архив директории, миграция старых `.taskData.json`, Oracle, хранилище, сторонние проводники, тёмная тема, кросс-сборка Win↔Linux.
