# Task Number high-water mark

The Project counter is a high-water mark, not a “next free slot” scanner. It advances only when a Task is created with exactly the number the dialog proposed. A custom Number (any text, including another integer), Import, and bulk create leave the mark still; delete and archive do not roll it back. That way a typed `ABC` or an imported `10` does not steal the next proposed `5`, and removing a Task does not reuse its number.

If the proposed integer is already taken (manual create or Import used it while the mark lagged), the dialog walks forward to the first free whole number ≥ the proposal. The mark still moves only if the user saves that shown value.

Old Projects initialize the mark to the max of integer Numbers across all statuses, or 0, so the first proposal does not collide with existing `1…N`.

**Status:** accepted

## Alternatives rejected

- Always `max(integers)+1` on every create — Import and a typed `10` would jump the proposal past unused `5`.
- Rolling the mark back on delete — reuses Numbers and races with folders still on disk.
- Treating any saved integer as the new mark — a one-off `100` would skip 5–99 forever.
