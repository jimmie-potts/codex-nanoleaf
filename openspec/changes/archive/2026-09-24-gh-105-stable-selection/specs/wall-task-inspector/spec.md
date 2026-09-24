## MODIFIED Requirements

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
