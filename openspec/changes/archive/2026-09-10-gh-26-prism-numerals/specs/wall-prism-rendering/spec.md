## MODIFIED Requirements

### Requirement: Local interaction survives rendering
The wall SHALL preserve keyboard focus, Ctrl/Command/Shift multi-selection, task/project/inspector associations, selection and pending rings, explicit Locate, and Classic/Project allocation semantics. The renderer SHALL NOT add state or device writes. Luminous numerals SHALL follow the wall identification visibility and clearance contract. Covers issue #53 AC6 and issue #26 AC3, AC4 and AC6.

#### Scenario: Select during an update
- **WHEN** a poll or material update occurs while a Line is focused or several Lines are selected
- **THEN** the same physical IDs retain focus/selection and no Locate, unread, assignment or light request is issued

#### Scenario: Selection interrupts assembly
- **WHEN** an interaction selects a Line before assembly finishes
- **THEN** the structure settles immediately, the intended physical Line is selected, and its current numeral is visible in the completed layout without a stale label or discarded action
