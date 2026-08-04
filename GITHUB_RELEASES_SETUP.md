# Публикация релизов TaskManager на GitHub

Временная инструкция. После настройки CI/релизов файл можно удалить.

## 1. Версия

1. Поднимите версию в `pyproject.toml` (`[project].version`).
2. Синхронизируйте `_FALLBACK_VERSION` в `src/taskmanager/version.py`.
3. Закоммитьте и создайте git-тег вида `vX.Y.Z` (например `v0.2.0`).

```bash
git tag v0.2.0
git push origin v0.2.0
```

## 2. Сборка бинарников

Собирайте **на целевой ОС** (см. раздел «Сборка» в `README.md`):

| ОС | Имя asset |
|----|-----------|
| Linux | `TaskManager` |
| Windows | `TaskManager.exe` |

Артефакты лежат в `dist/`.

## 3. GitHub Release

1. Откройте репозиторий → **Releases** → **Draft a new release**.
2. **Choose a tag**: `vX.Y.Z` (тот же, что в шаге 1).
3. Заголовок: например `TaskManager X.Y.Z`.
4. Приложите оба файла: `TaskManager` и `TaskManager.exe` (имена без суффиксов версии).
5. Опубликуйте release (**Publish release**).

API проверки обновлений:

`GET https://api.github.com/repos/ShiragG/TaskManager/releases/latest`

Приложение сравнивает `tag_name` с текущей версией и предлагает скачать нужный asset через «Сохранить как…» (самозамены exe нет).
