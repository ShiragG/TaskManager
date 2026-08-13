# Reminders are not Срок

A Reminder is a scheduled ping (text, local time, repeat rule), not the Task’s optional due date. Срок stays a date-only field for “when the work should be done”; mixing the two would make overdue highlighting and calendar pings fight over the same column.

Missed is only the latest past occurrence that is not skipped and not acknowledged — one row per series, so a weekly ping that fired for months does not flood the list. A short month without the chosen day (31st in February) has no occurrence that month. Archive and delete destroy the series; Restore does not bring it back. Notifications run only while the process is open (timer + OS toast / in-app popup); there is no background tray that keeps the app “alive” after the window closes.

**Status:** accepted

## Alternatives rejected

- Reusing Срок as the ping time — loses “due date without a clock” and couples row color to reminders.
- Showing every unacked past fire — unbounded missed list.
- Rolling a 31st into the last day of a short month — invents occurrences the rule did not schedule.
- Keeping reminders on Restore — archive was an explicit end of the series.
- Minimize-to-tray / run without a window — rejected; the process is the session.
