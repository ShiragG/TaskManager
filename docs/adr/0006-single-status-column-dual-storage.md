# Single status column, dual storage

A Task shows one **Статус** column after the number. Linked Tasks display a Source status snapshot; local Tasks display Workflow status. Both are stored on the row (`workflow_status` always; `source_status_id` / `source_status_label` when linked) so clearing the source link restores an editable Workflow without losing the last source labels until cleared, and Import/Refresh can update the snapshot without a second UI column.

**Status:** accepted

## Alternatives rejected

- Two columns — noisy for mixed projects and for Tasks that never have a source.
- Overwriting one TEXT field for both meanings — loses Workflow when linking and makes “clear source → edit again” ambiguous.

## Consequences

- UI and Excel-style surfaces that need a single label use `Task.display_status`.
- Workflow is editable only without `has_source`; Source status is never mass-edited from the table.
