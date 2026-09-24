# Wall task inspector Specification

## Purpose

Make retained map tasks easy to inspect in a compact list without hiding their total, duplicating waiting rows, or changing task state.

## Requirements

### Requirement: Compact rows retain truthful full-set counts
The inspector SHALL show up to one task per selected-device Line by default (or all retained tasks when fewer exist) and expose the total retained task count, per-status counts, waiting count, and number of rows shown. Counts SHALL use the full selected-device task projection before presentation filtering. Every retained task SHALL remain reachable through a labelled full-list control and filters. Covers issue #77 AC1 and AC3.

#### Scenario: Zero, eight, fifteen, and seventy-two tasks
- **WHEN** accepted snapshots contain zero, eight, fifteen, or seventy-two tasks with fifteen Lines
- **THEN** the initial list shows zero, eight, fifteen, or fifteen rows respectively, with accurate full-set status and waiting counts
- **AND** revealing the full list allows every retained task to be inspected and filtered

#### Scenario: Selected-device Line count changes
- **WHEN** the selected snapshot changes its Line count
- **THEN** the default task limit follows that count, including zero, while full-list access and truthful task counts remain available

#### Scenario: Desktop grid needs no task scrolling
- **WHEN** the current fifteen-Line wall is inspected at 1440×900 or 1280×800 with at least fifteen retained tasks
- **THEN** all fifteen compact task tiles are visible in two columns without scrolling the task area, including when a task is selected or tasks are waiting
- **AND** task titles remain accessible in full through selection or accessible names while compact tiles may truncate their visible titles

#### Scenario: Waiting has one row location
- **WHEN** tasks wait for a Line or change placement
- **THEN** waiting is summarized once and each displayed task has only one full row with its current Line badge or waiting label

### Requirement: Priority and filtering preserve access
The inspector SHALL order tasks by blocked, question, working, and unread status, with deterministic identity order within each group. Selecting or clearing a task or Line SHALL highlight associations without changing any row's position. Filters SHALL support status, waiting placement, and task text while leaving the underlying task set intact. A selected task outside the current view SHALL have an explicit way to reveal it. Covers issue #77 AC1, AC2, and AC5 and issue #105.

#### Scenario: Stable mixed-status priority
- **WHEN** tasks arrive in arbitrary order and unchanged snapshots repeat
- **THEN** actionable tasks precede unread tasks and ties do not jump between polls

#### Scenario: Selection highlights in place
- **WHEN** the user selects a task, a Line badge, or several Lines, or clears the selection
- **THEN** the selected rows are highlighted and every row keeps its position

#### Scenario: Filtered selected task
- **WHEN** a filter or compact limit excludes a selected task
- **THEN** the inspector explains that selected tasks are outside the view and provides a keyboard-accessible way to reveal them without reordering the compact view

### Requirement: Polling preserves ongoing inspection
Status and placement changes SHALL preserve keyboard focus for a retained task, local task/Line selection, task details, and, in Project layout, an in-progress project override. Polling SHALL NOT deliberately scroll the user to reordered rows. A focused retained row that leaves a filter SHALL remain usable until focus leaves, with its exception reflected in the shown count. Covers AC2 and AC3.

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
The compact and full views SHALL support keyboard controls, missing project metadata, long labels, narrow viewports, and reduced motion without horizontal page overflow or motion required to inspect a task. Narrow screens SHALL retain readable page flow and MAY require vertical page scrolling. Covers AC4.

#### Scenario: Narrow view with absent metadata
- **WHEN** many tasks have fallback labels and no known project at a 390-pixel viewport with reduced motion
- **THEN** counts, list controls, task titles, and placement labels remain readable and operable

### Requirement: Qualified Desktop thread navigation
The wall context card SHALL offer a labelled, keyboard-reachable **Open in Codex** anchor without a target only when `/api/state` supplies a server-built `codexUrl`. The server SHALL validate a hyphenated UUID before building `codex://threads/<uuid>`. Legacy tasks SHALL qualify only when their ID is present in the configured Desktop title index. Shared eligibility SHALL follow the shared-session-consumer root-identity rule. Other tasks SHALL have no link. The card SHALL refresh when its URL changes, appears or disappears. Covers #108 AC1, AC2, AC3 and AC6.

#### Scenario: Indexed legacy Desktop thread
- **WHEN** a legacy task with a UUID in the configured Desktop index is selected
- **THEN** its context card has an Open in Codex link to that UUID, reachable by keyboard without horizontal overflow at a narrow viewport
- **AND** activation in the Windows browser opens that thread through the Codex Desktop protocol handler

#### Scenario: Ineligible or changing task
- **WHEN** a task has an unknown or malformed ID, or a subsequent snapshot removes its eligibility
- **THEN** the context card contains no Open in Codex link
- **AND** a later qualified URL appears without requiring reselection

### Requirement: Navigation preserves read ownership
Activating the link SHALL send no request to the map server and SHALL perform no bridge write, unread acknowledgment, Locate or device request. Selecting in the map SHALL NOT mark a task read. Codex SHALL own marking its thread read, followed by the existing unread reader. The footer and bridge guide SHALL explain this distinction and the guide SHALL describe link eligibility. Covers #108 AC4, AC5 and AC7.

#### Scenario: Open an unread task
- **WHEN** the user opens an unread task through its link
- **THEN** the map makes no action request and does not clear the task itself
- **AND** unread clearing occurs only after the existing reader observes Codex's read evidence
