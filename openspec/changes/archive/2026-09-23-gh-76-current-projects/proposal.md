## Why

Saved project preferences currently fill the map even when no displayed task uses them. [Issue #76](https://github.com/jimmie-potts/codex-nanoleaf/issues/76) requests a useful current-project view without deleting those preferences.

## What Changes

- Show projects associated with the full retained map task list, ranked by active-status count, unread count, then name.
- Provide a saved-project disclosure and an honest empty state when associations are absent.
- Preserve open color controls, focus, selection, pending edits, global preferences, and the distinct Shared pool while task membership changes.
- Keep existing task lifecycle, attribution, reservation allocation, and protected write endpoints unchanged.

## Capabilities

### New Capabilities

- `wall-current-projects`: current-project eligibility, ordering, saved-project access, and interaction preservation. Retains the existing color-editing contract from the bridge guide and composes the existing Line identification contract.

### Modified Capabilities

None.

## Impact

Browser presentation in `bridge/wall.html`, synthetic browser coverage, isolated Python state checks, and the bridge guide's capability link. No API schema, database migration, collector, device writer, or new session clock. Hub #195 and #218 own retirement; #75 owns missing attribution; #44 owns selector presentation. Fixtures cover missing and recreated records independently of those deliveries.
