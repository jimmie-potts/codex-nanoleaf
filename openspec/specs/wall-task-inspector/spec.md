# Wall task inspector Specification

## Purpose

Make retained map tasks easy to inspect in a compact list without hiding their total, duplicating waiting rows, or changing task state.

## Requirements

### Requirement: Compact rows retain truthful full-set counts
The inspector SHALL show at most eight task rows by default and expose the total retained task count, per-status counts, waiting count, and number of rows shown. Counts SHALL use the full selected-device task projection before presentation filtering. Every retained task SHALL remain reachable through a labelled full-list control and filters. Covers issue #77 AC1 and AC3.

#### Scenario: Zero, eight, and seventy-two tasks
- **WHEN** accepted snapshots contain zero, eight, or seventy-two tasks
- **THEN** the initial list shows zero, eight, or eight rows respectively, with accurate full-set status and waiting counts
- **AND** revealing the full list allows every retained task to be inspected and filtered

#### Scenario: Waiting has one row location
- **WHEN** tasks wait for a Line or change placement
- **THEN** waiting is summarized once and each displayed task has only one full row with its current Line badge or waiting label

### Requirement: Priority and filtering preserve access
The inspector SHALL prioritize selected tasks, then blocked, question, working, and unread tasks, with deterministic identity order within each group. Filters SHALL support status, waiting placement, and task text while leaving the underlying task set intact. A selected task outside the current view SHALL have an explicit way to reveal it. Covers AC1, AC2, and AC5.

#### Scenario: Stable mixed-status priority
- **WHEN** tasks arrive in arbitrary order and unchanged snapshots repeat
- **THEN** selected and actionable tasks precede unread tasks and ties do not jump between polls

#### Scenario: Filtered selected task
- **WHEN** a filter or compact limit excludes a selected task
- **THEN** the inspector explains that selected tasks are outside the view and provides a keyboard-accessible way to reveal them

### Requirement: Polling preserves ongoing inspection
Status and placement changes SHALL preserve keyboard focus for a retained task, local task/Line selection, task details, and an in-progress project override. Polling SHALL NOT deliberately scroll the user to reordered rows. A focused retained row that leaves a filter SHALL remain usable until focus leaves, with its exception reflected in the shown count. Covers AC2 and AC3.

#### Scenario: Selected task moves or waits
- **WHEN** a task selected by its title changes Line or becomes waiting
- **THEN** task selection and details follow that task, its single row updates placement, and keyboard focus remains usable

#### Scenario: Focused task changes status
- **WHEN** a focused task changes priority or no longer matches the active filter
- **THEN** its keyboard control remains reachable, other rows update, and the current scroll position is preserved where content size permits

### Requirement: Owner retirement removes rows without UI side effects
The inspector SHALL remove owner-retired rows and their counts on the next accepted snapshot, clear obsolete task selection/details, and return focus to a surviving control when necessary. Fresh recreation SHALL use only the new snapshot. Opening, filtering, or selecting the list SHALL issue no write, unread acknowledgment, Locate, or device request and SHALL add no lifecycle clock. Covers AC5 and the current-session boundary.

#### Scenario: Retirement and fresh recreation
- **WHEN** the selected or focused task disappears from the retained projection and later reappears
- **THEN** it is absent in the intervening list and counts, stale details/overrides are unavailable, and recreation does not restore obsolete local task selection

### Requirement: Compact inspection remains accessible
The compact and full views SHALL support keyboard controls, missing project metadata, long labels, narrow viewports, and reduced motion without horizontal page overflow or motion required to inspect a task. Covers AC4.

#### Scenario: Narrow view with absent metadata
- **WHEN** many tasks have fallback labels and no known project at a 390-pixel viewport with reduced motion
- **THEN** counts, list controls, task titles, and placement labels remain readable and operable
