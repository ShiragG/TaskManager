# Row highlights stay in separate places

A task row can show four signals at once. Each keeps its own place so none of them covers the others: **Цвет заявки** is the row background, Priority fills only the Priority cell, **Цвет статуса** is a round mark beside the status label, and a **Срок** warning colors only the date text. The warning used to recolor the whole row, which hid **Цвет заявки** and the priority digit.

**Status:** accepted

## Alternatives rejected

- Filling the status cell — that covers **Цвет заявки** in that cell and reads as a second row color.
- A stripe on the left instead of the row background — **Цвет заявки** would no longer be the color of the row.
- Painting the whole Excel row with the warning color — the file would keep hiding **Цвет заявки** the same way the old table did.

## Consequences

- **Цвет статуса** is drawn only on a linked Task, and only when that module's highlight is on and that status id has a color. Workflow status is not a **Цвет статуса**. **Цвет статуса работы** is a separate optional color from settings; the same circle is drawn only on a Task without a source, and only when that highlight is on and that status has a color.
- The same status colors apply in every project. Turning a module off does not hide marks for tasks that already carry its status snapshot. Uninstalling a module does not delete the colors; installing that id again uses them.
