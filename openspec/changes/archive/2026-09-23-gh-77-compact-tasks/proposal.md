## Why

The inspector renders every task and repeats waiting rows, making attention harder to find. [Issue #77](https://github.com/jimmie-potts/codex-nanoleaf/issues/77) requests a compact view with full access and truthful counts.

## What Changes

- Default to eight prioritized task rows with total, status, shown, and waiting counts.
- Add a full-list control with status/waiting and text filters; keep each task in one row location.
- Preserve local selection, details, manual overrides, keyboard focus, and scroll position across polling, placement, retirement, and recreation.
- Retain the full API task set, existing lifecycle/projection, allocation, and passive-selection boundary.

## Capabilities

### New Capabilities

- `wall-task-inspector`: compact/full task presentation, counts, filters, stable ordering and interaction recovery. Composes existing task placement and passive selection requirements from `wall-line-identification`.

### Modified Capabilities

None.

## Impact

Browser HTML and deterministic browser tests; bridge guide links the new presentation contract. No API, database, Python, device, or metadata changes. #74 supplies existing parent/child projection; Hub #195/#218 supply owner-authorized removal. No archive browser or second expiration clock.
