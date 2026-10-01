# Task Description and Comment are markdown

Description and Comment are the Task's own text. They were stored as HTML from a Qt rich-text editor, which made the database the owner of a widget format: agents and the CLI had to escape tags, underline could not round-trip through markdown, and preview depended on `QTextDocument`. The canon is now markdown in those same columns. Rendering uses a markdown library (tables, strikethrough, task lists, single-newline breaks). An embedded browser was the other way to show that set, and it would pull a second document engine into a desktop app that already draws text with Qt. Event text stays on the HTML editor; it is not Description or Comment.

**Status:** accepted

## Considered Options

- **Keep HTML** — matches the old editor, but the stored string is Qt's serialization. Search, export, and the CLI all grow special cases, and a later switch still has to migrate every row.
- **Embedded browser** — renders markdown faithfully, including things this app does not support (mermaid, callouts). It adds a browser runtime for two text fields.
- **Markdown in the existing columns** — one text format for the GUI, the CLI, and agents. Preview is generated HTML for Qt, not the stored value. Underline, mermaid, callouts, and wiki links are out of scope.

## Consequences

- Opening a database migrates existing Description and Comment HTML once. Formatting markdown can represent is kept; `file://` images under `.images/` become relative links; underline is dropped. Plain-text columns are recomputed from the markdown so search does not match tags.
- The change is hard to reverse: after migration the original HTML is gone, and new writes are markdown. A return to HTML would be another lossy pass.
- Import and Refresh from source write the Source item's text as markdown. They do not wrap it in HTML.
