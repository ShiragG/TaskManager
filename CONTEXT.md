# TaskManager

Desktop application for organizing work requests with metadata in SQLite, optionally backed by folders on disk, grouped into projects.

## Language

**Task** (заявка):
A work request represented by a SQLite record; an on-disk folder is optional (`has_folder` plus presence under the work directory).
_Avoid_: ticket, issue, case, job

**Project** (проект):
A named grouping of tasks shown as a tab in the main window; may map to a folder under the work directory when foldered tasks need one.
_Avoid_: directory, folder (for the grouping), workspace, category

**Comment** (комментарий):
An HTML field on a task stored in SQLite; distinct from the optional Notes file on disk.
_Avoid_: notes, description (task short text), memo

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

**Folder name**:
The on-disk name of a task folder when one exists, equal to the task **number** (sanitized). When the number changes and a folder is present, the folder is renamed and `folder_name` is updated in SQLite. Description is metadata only and is not part of the folder name.
_Avoid_: path, title, display name

**Hidden** (скрытая):
A task flag: in the default view the task is omitted; in «Скрытые» mode only hidden active tasks are listed. Mutually exclusive with archive browsing mode.
_Avoid_: archived (different concept), deleted, inactive

**Notes file** (файл заметок):
An optional `Notes.txt` in the task folder, created at task creation with a dated header when a folder is created; paired with a Link named «Заметки» pointing at the absolute path. Unavailable when the task has no folder. Existing `Notes.txt` is never overwritten.
_Avoid_: memo, comment, description (task metadata)

**Priority** (приоритет):
An integer urgency score on a task from 0 (critical) to 10 (calm). Distinct from the task row Color.
_Avoid_: severity, importance, rank, color
