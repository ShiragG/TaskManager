# TaskManager

Desktop application for organizing work requests as folders on disk, grouped into directories, with metadata in SQLite.

## Language

**Task** (заявка):
A work request represented by a folder on disk and a matching SQLite record.
_Avoid_: ticket, issue, case, job

**Directory** (директория):
A named grouping of tasks shown as a tab in the main window; maps to a folder under the work directory.
_Avoid_: folder (for the grouping), project, workspace, category

**Archive**:
The inactive state of a task: status `archived` plus physical move of its folder under the archive root by month (`YYYY_MM`).
_Avoid_: delete, trash, close

**Template**:
A directory-local folder whose contents are copied when creating a task from a template.
_Avoid_: skeleton, scaffold, boilerplate

**Link**:
A named URL or filesystem path attached to a task and stored in SQLite.
_Avoid_: shortcut, bookmark, reference

**Work directory**:
The root filesystem path under which directories, templates, and the archive live.
_Avoid_: workspace root, project root, home

**Folder name**:
The on-disk name of a task folder, equal to the task **number** (sanitized). When the number changes, the folder is renamed on disk and `folder_name` is updated in SQLite. Description is metadata only and is not part of the folder name.
_Avoid_: path, title, display name

**Hidden** (скрытая):
A task flag: in the default view the task is omitted; in «Скрытые» mode only hidden tasks are listed.
_Avoid_: archived (different concept), deleted, inactive

**Notes file** (файл заметок):
An optional `Notes.txt` in the task folder, created at task creation with a dated header; paired with a Link named «Заметки» pointing at the absolute path. Whether to create it by default is a setting; the create-task dialog exposes a checkbox. Existing `Notes.txt` is never overwritten.
_Avoid_: memo, comment, description (task metadata)

**Priority** (приоритет):
An integer urgency score on a task from 0 (critical) to 10 (calm). Distinct from the task row Color.
_Avoid_: severity, importance, rank, color
