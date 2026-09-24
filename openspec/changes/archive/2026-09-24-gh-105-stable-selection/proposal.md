## Why

Clicking a task in the wall map inspector moves it to the first position of the task grid, so the list shifts under the pointer. [Issue #105](https://github.com/jimmie-potts/codex-nanoleaf/issues/105) asks for selection to highlight a task in place. The selected-first ordering came from #77.

## What Changes

- Remove selection from inspector ordering. Rows sort only by status priority (blocked, question, working, unread) with identity ties.
- Selecting or clearing a task, Line badge, or several Lines changes highlights and details only, never row positions.
- A selected task that a filter or the compact limit hides stays reachable through the existing note and **Show selected tasks** control. The compact view does not promote it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `wall-task-inspector`: the "Priority and filtering preserve access" requirement no longer ranks selected tasks first.

## Impact

`bridge/wall.html` ordering, the compact-task browser check, and the bridge guide sentence describing the order. No API, Python, state, or device changes. Selection stays passive.

## Design

Omitted. The change removes one sort key in a single function and meets none of the schema's design criteria: no cross-cutting change, new dependency, data migration, or unresolved technical decision.
