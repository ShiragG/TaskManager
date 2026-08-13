# TaskManager

Desktop application for organizing work requests with metadata in SQLite, optionally backed by folders on disk, grouped into projects.

## Language

**Task** (заявка):
A work request represented by a SQLite record; an on-disk folder is optional (`has_folder` plus presence under the work directory).
_Avoid_: ticket, issue, case, job

**Project** (проект):
A named grouping of tasks shown as a tab in the main window; may map to a folder under the work directory when foldered tasks need one.
_Avoid_: directory, folder (for the grouping), workspace, category

**Archive**:
The inactive state of a task: status `archived`, with a physical folder move under the archive root as `{YYYY_MM}/{archive_project_folder}/{folder_name}` only when the task has a folder (`archive_project_folder` is the sanitized project name snapshotted at archive time; renaming the project later does not move archived folders). Archive can be browsed and a task **Restored** (returned to active).
_Avoid_: delete, trash, close

**Template**:
A project-local folder whose contents are copied when creating a foldered task from a template.
_Avoid_: skeleton, scaffold, boilerplate

**Link**:
A named URL or filesystem path attached to a task and stored in SQLite.
_Avoid_: shortcut, bookmark, reference

**Work directory**:
The root filesystem path under which project folders, templates, and the archive live when used.
_Avoid_: workspace root, project root, home

**Number** (номер):
The Task identifier unique within a Project (text; also the folder name). Autofill proposes the next whole number after the Project high-water mark; the mark advances only when a Task is created with that proposed number.
_Avoid_: id, title

**Folder name**:
The on-disk name of a task folder when one exists, equal to the task **Number** (sanitized). When the number changes and a folder is present, the folder is renamed and `folder_name` is updated in SQLite. Description is metadata only and is not part of the folder name.
_Avoid_: path, title, display name

**Срок**:
An optional date on a Task (no time of day) when the work should be done. Distinct from an Event.
_Avoid_: reminder, event, deadline (as a separate entity)

**Event** (событие):
A calendar record (text, local date/time, repeat rule) that may be linked to a Task. Not Срок and not a notification toast; the Calendar window is where occurrences are browsed. The UI never says «серия» — delete is «Удалить событие»; snooze («Напомнить через») delays a ping and is not a second entity.
_Avoid_: reminder, серия, срок, toast, notification (the UI chrome)

**Hidden** (скрытая):
A task flag: in the default view the task is omitted; in «Скрытые» mode only hidden active tasks are listed. Mutually exclusive with archive browsing mode.
_Avoid_: archived (different concept), deleted, inactive

**Notes file** (файл заметок):
An optional `Notes.txt` in the task folder, created at task creation with a dated header when a folder is created; paired with a Link named «Заметки» pointing at the absolute path. Unavailable when the task has no folder. Existing `Notes.txt` is never overwritten.
_Avoid_: memo, comment, description (task metadata)

**Priority** (приоритет):
An integer urgency score on a task from 0 (critical) to 10 (calm). Distinct from the task row Color.
_Avoid_: severity, importance, rank, color

**Description** (описание):
Task body text stored in SQLite (HTML in the UI); on Import or Refresh from source it may be wholly replaced from a Source item.
_Avoid_: comment

**Comment** (комментарий):
Personal HTML notes on a Task in SQLite; never filled from a Source item and never overwritten by Refresh from source. Distinct from the optional Notes file on disk.
_Avoid_: notes, description, memo

**Source module** (модуль источника):
An optional in-process plugin that reads external work items while TaskManager runs. Without installed/enabled modules, locally created Tasks work as usual; Import / Refresh from source are unavailable.
_Avoid_: integration, connector, ticket API

**Source item** (элемент источника):
A record in an external system before it becomes a Task.
_Avoid_: заявка, Task, ticket (for the external object)

**Workflow status** (статус работы):
Closed local set on a Task without a source link: Новая, В работе, Ждёт, Готово, Отменена. Independent of Archive; not shown or edited when the Task has a source link.
_Avoid_: Source status, archive, Task status

**Source status** (статус источника):
A Source module catalog entry (`id` + label; `default_selected` for Import filters). On a linked Task, also the read-only snapshot of that id/label written on Import and Refresh from source (not background sync).
_Avoid_: Workflow status, archive

**Source priority** (приоритет источника):
A catalog entry from a Source module whose `mapped_priority` is already on the Task **Priority** scale (0..10). Used when mapping a Source item into a Task; not a separate Task field.
_Avoid_: severity, Razr-native priority id as Task priority

**Module registry** (реестр модулей):
SQLite rows for installed Source modules (id, GitHub repo, display name, enabled, version, update descriptor). Credentials stay in `source_credentials`; the registry is not `settings.json`.
_Avoid_: settings list, plugin folder alone as source of truth

**Import**:
Bringing a Source item into the current Project as a Task. The single path snapshots the item into the create-Task dialog; the bulk path creates Tasks from snapshots without that dialog (settings defaults for folder/notes; honors «Скачать файлы…»). A Source item is already imported when the Project has a Task with the same `(source_module_id, external_id)` (any status/hidden). Status/priority catalogs are session-cached by the host; on catalog failure Import shows an error and does not call `list_items`.
_Avoid_: sync, clone

**Refresh from source**:
A manual overwrite of the mapped Task fields from the Source item.
_Avoid_: sync, pull all
