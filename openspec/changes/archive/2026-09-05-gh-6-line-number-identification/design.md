## Context

See [the proposal](proposal.md) for motivation. `/api/state` supplies stable physical `id`/`number` pairs, saved `line.project` ownership, and current `line.task`/`task.line`/`task.project` associations. The page already numbers the SVG but summarizes project rows with counts. Task rows have no placement label. Polling rebuilds task rows every second.

This design records the UI association and focus decisions before coding. They are the schema's conditional reason to include a design; no backend design or migration is involved.

## Goals / Non-Goals

Use the existing snapshot consistently across the page while keeping selection independent of mutation controls. Keep the server, allocator, worker, persistence, and installation unchanged.

## Decisions

- Resolve badge numbers from `state.lines`, keyed by physical ID. Do not compute numbers from DOM order, transformed coordinates, project order, or task order.
- Show separate Reserved and In use groups in Project rows. A Line can appear in both when its project uses its own reservation. This makes an idle reservation distinguishable from current usage. A combined count or unlabeled badge list would conceal the distinction.
- Mark Shared usage in the owning project's In use badge. Show the Shared pool's occupied and available Lines in Project. Classic omits reservation groups and the reservation-based pool, because all Lines participate in its automatic allocation.
- Derive highlights from selected physical IDs plus the currently focused waiting task. In Project, highlight both the saved owner/pool and any current task's project; in Classic, highlight the task's project alone. This also handles a deferred reassignment without presenting a proposed placement as current.
- Use native buttons for numbered badges and task titles. Preserve unchanged row DOM across polling, update association classes separately, and preserve meaningful focus when row content changes. Selection does not call the existing write helper. Task selection without a placement clears stale Line selection.
- Keep pending reservation arrows; expand task-override notices with the task's current Line and destination. A return to Codex assignment is labeled as such because its resolved destination can differ from the current manual override.

## Risks / Trade-offs

- More badges can lengthen project rows. Use wrapping groups inside the existing scroll area and inspect desktop, compact, and mobile widths.
- Refreshes can make cached highlights stale or destroy keyboard focus. Test unchanged polling, moved tasks, changed project membership, and waiting tasks.
- Real device state is unavailable in source-only validation. Browser tests use synthetic API state; the existing Python Locate tests cover worker restrictions without a device. Installation and physical observations remain separate.

## Migration Plan

No state migration. Synchronize the new capability, remove competing wall selection/Locate prose from the bridge guide, and link to the reviewed specification. Unmigrated bridge behavior retains its existing documentation owner. The source merge does not update the installed bridge.
