## Context

See proposal.md. `inspect()` fills a selection card and rebuilds a separate detail card behind a fingerprint, defers rebuilds while the override select is focused, and `drawTasks()` moves both cards around the task card between compact and full views. Ten browser suites click `#classic`, `#project`, `#coverage`, `#clear`, `#assign`, `#swap` or the override select, some in Classic. The owner's decisions are recorded in issue #135.

## Goals / Non-Goals

Show one context card with only the controls that act in the current layout and mode, keep every existing endpoint and behavior, and keep focus preservation through polling. Do not change allocation, attribution, the bridge contract, the machine API or the #77 task grid; do not add per-task pinning.

## Decisions

- One `#contextCard` keeps `#selectionTitle`, `#selectionHint`, `#taskDetail` and `#selectionBody` inside it, so existing focus and fingerprint logic survives with element identities intact. The card heading names the Line or Lines; the task block holds the title once. The hint no longer repeats the task title or project: it counts several selected Lines, explains how to select when nothing is chosen, and is otherwise hidden; the reservation shows in its own row in Project layout.
- A Reserved for row holds the reservation select above the task block and is shown only while `state.settings.style === 'project'` and Lines are selected; changing it sends the existing assignment request for every selected Line, so the Reserve button goes. Several Lines with different reservations show a disabled "Several reservations" option. The select resyncs from polled state whenever it is not focused, so a rejected edit cannot linger. Swap halves stays in the actions row, hidden outside Project layout. The map no longer renders the task override; the `/api/task` endpoint, pending-edit labels and the integration-settings extension are untouched.
- Layout buttons and Coverage move into a Layout group in Options. Coverage is hidden, not disabled, in Classic. The `#classic` and `#project` ids and the settings request are unchanged.
- `clearSelection()` replaces the Clear button. One keydown handler orders Escape: close Options if open, otherwise clear the selection unless focus is inside the task filters. A click on the wall host that is not on a Line, its hit layer or a number tag also clears. Focus returns to the wall heading, which gains `tabindex="-1"`.
- The Locate hint is rendered only in Free with the disabled button's explanation.
- Suites that need the reservation control set their fixture to Project layout explicitly; suites that cleared selection press Escape; the checks that exercised the override now exercise the reservation select or the task tile.

## Risks / Trade-offs

- Escape has two meanings in sequence (menu, then selection). The test asserts the order.
- Hiding rather than removing the Project-only controls keeps a little dead markup in Classic; it avoids rebuilding the card on layout changes and keeps ids stable.
- Draft PR #116 changes the override's blur handler; this candidate keeps main's handler and the later merge refreshes its comparison.
