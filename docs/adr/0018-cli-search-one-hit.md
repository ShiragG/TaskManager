# One search hit is a full Task; several hits are partial rows

`task search` always prints a JSON array. Zero hits are `[]`. One hit is a one-element array of the same object as `task get`, including the full markdown `description` and `comment`. Several hits are short rows with `partial: true` and a `snippet` (the first 160 characters of one field, with `…` when the field is longer). Those rows omit `description` and `comment`.

The same keys cannot mean a clipped string on one row and the full markdown on another. `partial` is the signal to call `task get`. `task list` is always short rows, even when the project has a single Task: the project is already the argument, and the command is a list, not a lookup.

**Status:** accepted

## Considered Options

- **Always full objects** — one shape, but a broad query dumps every Description and Comment.
- **Always snippets, including a single hit** — the caller would `get` even when search already found the only Task.
- **Truncate `description` / `comment` in place when there are many hits** — a short Task is indistinguishable from a clipped one.
- **Full object for one hit, `partial` rows for many** — the one-hit case needs no second call; many hits stay small and unambiguous.

## Consequences

- `task get`, create, update, archive, restore, hide, link add/remove, and a one-hit search return the full Task object. `description_plain` and `comment_plain` are not in that object. `description` and `comment` stay markdown; HTML left from before the markdown migration still goes through the current CLI display.
- `task comment set` and `append` return only `project`, `number`, and `comment`. Append's comment already includes the `## YYYY-MM-DD HH:MM` heading.
- A short row always has `partial: true`, even when the text is shorter than 160 characters, because the row has no folder, no links, and only one text field. List snippets start at Description, or at Comment when Description is empty. Search snippets come from the field that contains the query (`casefold`); if both do, Description; if only the number matched, the same rule as list. Search rows include `project`. List rows do not. `status` on a short row is `active` or `archived`. `source_status_label` is null when the Task has no source.
- `--human` list and search stay tables. The status column is the window label (`display_status`). One snippet column replaces the two text columns. Default JSON is unchanged by `--human`.
- `--description -` and `--comment -` on create and update read stdin. Both at once is a usage error: one call, one stdin. A missing flag still means “do not change” on update and an empty string on create.
