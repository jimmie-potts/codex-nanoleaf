# 0012. The wall map shows status first; layout and placement editing are secondary

Status: Accepted for source implementation in [#135](https://github.com/jimmie-potts/codex-nanoleaf/issues/135).

## Context

The wall map grew a header row of Layout, Mode and Coverage controls, a wall toolbar of secondary controls, and an inspector with two cards for one selection: a selection card with a reservation select, Assign, Clear selection, Swap halves and Locate, and a detail card with the task and a project override. [#78](https://github.com/jimmie-potts/codex-nanoleaf/issues/78) moved the wall toolbar's controls under one Options menu and gave counts and hints one home each. Reviewing that result on 2026-09-24, the owner found the inspector still cluttered and its reservation and override controls not useful in their current form.

The installation is one operator, one Linux runtime and one registered Lines wall. A read-only look at its map state that day showed Classic layout, 15 Lines, 10 tasks, 34 projects synced from Codex, no reservations, no swapped halves and no overrides, with 7 of 10 tasks attributed automatically. Reservations, half choices and the override only change what the wall does in Project layout; in Classic, the upgrade default, placement is automatic and reservations are saved but ignored. That is also why an earlier manual Line assignment appeared to do nothing.

## Decision

The map's default screen is a status display. Layout switching and placement editing are secondary, reachable but not shown by default.

- The header holds the Mode controls, the live readout and the connection state. The Layout switch moves into the Options menu; Coverage appears there only while Project layout is active.
- One context card shows the selected Line or Lines, the task's title, status, project, elapsed time and Open in Codex link, then Locate. The task's title and project appear once outside the task tiles.
- In Classic no reservation, half-swap or override control is shown. In Project layout the context card adds the reservation select with a Reserve action, Swap halves and the task's project override, through the existing endpoints and pending-edit rules.
- Clear selection goes; Escape or a click on empty wall canvas clears the selection and returns focus to the wall heading. The Locate explanation appears only in Free.
- Orientation keeps its current default and its saved per-device settings.
- The bridge, the CLI `style` command and the integration-settings extension keep Project layout, reservations and overrides unchanged. Placement stays automatic in Classic.

Vocabulary: "layout" in user-facing text, while code and the CLI keep `style`; "reservation" for a Line saved for a project, with the action named Reserve rather than Assign; "attribution" for the automatic task-to-project lookup and "override" for the manual one; "context card" for the merged card; "Options" for the wall's secondary controls.

## Consequences

The default screen has fewer controls and no repeated task text. Tasks with no attributed project stay "No project" in Classic, with no map control to change that. Per-task pinning is not offered. Both are recorded in #135 with their revisit triggers: the first time a Claude Code task must sit under a project, or the first time the owner wants a task on a specific Line. Retiring Project layout from the bridge, CLI and API is deferred until it stays unused after this change lands.

Browser suites that need reservation or override controls set Project layout explicitly; suites that cleared a selection press Escape. Draft PR #116, which changes the override's blur handler in the same file, refreshes its comparison after this change or vice versa.
