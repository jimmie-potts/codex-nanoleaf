## Context

See proposal.md. The API already returns the full saved catalog and device-scoped placement, and the browser reuses project rows. Its current fingerprint omits task status, and moving a focused row with insertBefore can disrupt native editing. These interaction details justify a design document.

## Goals / Non-Goals

Keep eligibility and ranking in the presentation, using tasks rather than stored project counters. Do not filter the API catalog: assignment controls still need saved projects. Do not change the allocator, shared owner, or persistent settings.

## Decisions

- Use one combined active-status count, followed by unread count and name/ID ties. This matches the issue's active-versus-unread priority. Unknown associations contribute to no project.
- Keep a collapsed-by-default saved-project disclosure. Expanded mode includes every saved project, with current projects first. The disclosure is local view state, not a saved global preference.
- Reuse rows by project identity. Include task status and disclosure/focus state in invalidation. Reorder siblings around the focused row instead of detaching it; retain a focused inactive row until blur. Preserve badge focus by its existing semantic key when refreshing Line details; if that badge disappears, focus the same project's color control.
- Keep the reservation selector's options stable when only task activity changes, preserving an unsubmitted selection.

## Risks / Trade-offs

- Native color dialogs are browser-managed → preserve their exact input and attached row; assert identity, focus and unsaved value during polling, then visually inspect the candidate. Automated browser checks cannot inspect an OS-native dialog's internals.
- Saved-project counts can exceed the default row count → label the disclosure with the complete catalog count and state when there are no current associations.
- Upstream retention is independently delivered → simulate authoritative disappearance/recreation; do not claim installed end-to-end expiration acceptance.

## Migration Plan

No data migration. Source-only delivery; a later authorized installation can replace the HTML. Reverting the presentation restores the old list without changing stored settings.
