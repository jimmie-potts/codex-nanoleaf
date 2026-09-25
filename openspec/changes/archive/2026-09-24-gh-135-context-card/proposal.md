## Why

The inspector still shows two cards for one selection, repeats the selected task's title and project, and offers reservation, half-swap and override controls that do nothing in Classic layout, the operator's default. [Issue #135](https://github.com/jimmie-potts/codex-nanoleaf/issues/135) records the owner's decisions of 2026-09-24: the default screen is a status display, layout switching and placement editing are secondary.

## What Changes

- Remove the Layout buttons and the Coverage select from the header; add a Layout group to the Options menu with Coverage shown only while Project layout is active.
- Merge the selection card and the task detail card into one context card: the selected Line or Lines, the task's title, status, project, elapsed time and Open in Codex link, then Locate. Waiting tasks, Lines without a task and multi-Line selections render conditional sections.
- Show a Reserved for select, applied on change, and Swap halves only while Project layout is active. Classic shows neither. The map no longer offers the per-task project override; the machine API keeps it.
- Remove Clear selection; Escape or a click on empty wall canvas clears the selection and returns focus to the wall heading. Show the Locate explanation only in Free.
- Record the decision in ADR 0013. The bridge, the CLI `style` command and the integration-settings extension keep Project layout, reservations and overrides unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `wall-map-hierarchy`: the default screen requirement moves Layout and Coverage out of the header; the Options requirement gains the Layout group; the counts-and-hints requirement names the context card and its reservation select; a new requirement owns the context card, layout-conditional editing controls, selection clearing and the Free-only Locate hint.
- `wall-line-identification`: the inspector identification requirement names the context card, limits reservation and half-swap controls to Project layout, and makes the reservation select apply on change.
- `wall-task-inspector`: the thread-navigation, polling and retirement requirements name the context card and drop the map's task override.

## Impact

`bridge/wall.html` markup, styles and the inspect, render, clearing and Options logic; the browser suites that clicked the header layout controls, Clear selection, Assign selected or the override; a new context-card browser check; the bridge guide; ADR 0013. No API, Python, state, database or device change. Draft PR #116 edits one line of the override handler in the same file; whichever merges second refreshes its comparison.
