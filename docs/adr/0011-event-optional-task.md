# Event may exist without a Task

An Event is a calendar record that **may** be linked to a Task. The link is optional and editable (choose, change, or clear on the Event form). Archive and delete of a Task still destroy its linked Events; Restore does not bring them back. Detach first if the Event should outlive the Task.

**Status:** accepted

## Alternatives rejected

- A second kind of record («личное», «встреча») — would split the calendar and the notify path; an Event without a Task already covers the case.
- Unlinking Events when a Task is archived or deleted — rejected; the Task still owns the lifetime of a linked Event. Detach explicitly to keep it.
