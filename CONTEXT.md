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
The on-disk name of a task folder, fixed at creation as `{number}___{description}` and not renamed by the application when metadata changes.
_Avoid_: path, title, display name
