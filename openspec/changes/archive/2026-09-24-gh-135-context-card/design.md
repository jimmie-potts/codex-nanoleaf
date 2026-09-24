## Context

See proposal.md. `inspect()` fills a selection card and rebuilds a separate detail card behind a fingerprint, defers rebuilds while the override select is focused, and `drawTasks()` moves both cards around the task card between compact and full views. Ten browser suites click `#classic`, `#project`, `#coverage`, `#clear`, `#assign`, `#swap` or the override select, some in Classic. The owner's decisions are recorded in issue #135.

## Goals / Non-Goals

Show one context card with only the controls that act in the current layout and mode, keep every existing endpoint and behavior, and keep focus preservation through polling. Do not change allocation, attribution, the bridge contract, the machine API or the #77 task grid; do not add per-task pinning.

## Decisions

- One `#contextCard` keeps `#selectionTitle`, `#selectionHint`, `#taskDetail` and `#selectionBody` inside it, so existing focus and fingerprint logic survives with element identities intact. The card heading names the Line or Lines; the task block holds the title once. The hint no longer repeats the task title or project: in Project layout it states the reservation, in Classic it is empty for a Line with a task.
- Reservation select, Reserve and Swap halves stay in `#selectionBody` and are hidden unless `state.settings.style === 'project'`; the override select is appended to the task block only in Project layout. Element ids stay, so the machine paths and pending-edit labels are untouched.
- Layout buttons and Coverage move into a Layout group in Options. Coverage is hidden, not disabled, in Classic. The `#classic` and `#project` ids and the settings request are unchanged.
- `clearSelection()` replaces the Clear button. One keydown handler orders Escape: close Options if open, otherwise clear the selection unless focus is inside the task filters. A click on the wall host that is not on a Line, its hit layer or a number tag also clears. Focus returns to the wall heading, which gains `tabindex="-1"`.
- The Locate hint is rendered only in Free with the disabled button's explanation.
- Suites that need the override or reservation controls set their fixture to Project layout explicitly; suites that cleared selection press Escape.

## Risks / Trade-offs

- Escape has two meanings in sequence (menu, then selection). The test asserts the order.
- Hiding rather than removing the Project-only controls keeps a little dead markup in Classic; it avoids rebuilding the card on layout changes and keeps ids stable.
- Draft PR #116 changes the override's blur handler; this candidate keeps main's handler and the later merge refreshes its comparison.
