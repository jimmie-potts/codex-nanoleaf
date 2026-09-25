## MODIFIED Requirements

### Requirement: Polling preserves ongoing inspection
Status and placement changes SHALL preserve keyboard focus for a retained task, local task/Line selection and task details. Polling SHALL NOT deliberately scroll the user to reordered rows. A focused retained row that leaves a filter SHALL remain usable until focus leaves, with its exception reflected in the shown count. Covers AC2 and AC3.

#### Scenario: Selected task moves or waits
- **WHEN** a task selected by its title changes Line or becomes waiting
- **THEN** task selection and details follow that task, its single row updates placement, and keyboard focus remains usable

#### Scenario: Focused task changes status
- **WHEN** a focused task changes priority or no longer matches the active filter
- **THEN** its keyboard control remains reachable, other rows update, and the current scroll position is preserved where content size permits

### Requirement: Owner retirement removes rows without UI side effects
The inspector SHALL remove owner-retired rows and their counts on the next accepted snapshot, clear obsolete task selection and details, and return focus to a surviving control when necessary. Fresh recreation SHALL use only the new snapshot. Opening, filtering, or selecting the list SHALL issue no write, unread acknowledgment, Locate, or device request and SHALL add no lifecycle clock. Covers AC5 and the current-session boundary.

#### Scenario: Retirement and fresh recreation
- **WHEN** the selected or focused task disappears from the retained projection and later reappears
- **THEN** it is absent in the intervening list and counts, its stale details are unavailable, and recreation does not restore obsolete local task selection

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
