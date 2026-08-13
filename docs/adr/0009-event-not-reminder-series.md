# Event, not Reminder series

The scheduled ping on a Task is an **Event** (событие). The window is **Календарь**. Repeat is a rule on that one Event, not a named «серия»; the UI deletes with «Удалить событие». «Напомнить через» (snooze) only delays the ping for the current occurrence — it is not a second stored entity. A monthly Event takes the day-of-month from **Дата** (a 31st in a short month is still skipped, ADR 0007). The glossary term Reminder is replaced; Срок stays a separate date-only field.

**Status:** accepted

## Alternatives rejected

- Keeping «напоминание» / «серия» in the UI — users treated a repeating Event as a list of objects to delete one-by-one.
- A separate snooze record in SQLite — would look like another Event and outlive the process; in-session delay is enough because notifications only run while the app is open.
- A dedicated «День месяца» control — duplicates Дата and invites a day that does not exist on the chosen calendar date.
