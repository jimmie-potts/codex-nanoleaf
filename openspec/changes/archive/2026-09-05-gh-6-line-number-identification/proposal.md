## Why

The wall numbers its physical Lines, but project and task rows do not identify those same Lines. [Issue #6](https://github.com/jimmie-potts/codex-nanoleaf/issues/6) owns the requested outcome and acceptance criteria AC1–AC5.

## What Changes

- Reuse the server's physical Line numbers in clickable project, Shared pool, and task badges.
- Show saved reservations separately from current task usage in Project; show current placements in Classic.
- Link selection across the wall, projects, and tasks, and name selected or pending Lines in the inspector and pending notice.
- Preserve the existing physical numbering, assignment rules, local selection behavior, explicit Locate restrictions, and bridge state.
- Migrate the wall identification and selection contract from the bridge guide into the first capability specification. Other bridge behavior remains owned by that guide.
- Record the user's delivery-policy refinement: all changes require PRs, and UI PRs need human approval before merging. This deliverable stops at a validated, independently reviewed PR awaiting that approval.

## Capabilities

### New Capabilities

- `wall-line-identification`: Physical numbering, project/task associations, local selection, and numbered inspector/pending labels. Includes the retained selection and Locate boundary under review alongside the new badges.

### Modified Capabilities

None. The current capability inventory is empty.

## Impact

The bundled `bridge/wall.html`, browser regression scenarios, and documentation links change. The existing `/api/state` already supplies physical IDs, numbers, reservations, and task placements; no API, database, allocator, worker, installer, or dependency change is needed. Delivery is source-only.
