## ADDED Requirements

### Requirement: Qualified Desktop thread navigation
The wall task detail card SHALL offer a labelled, keyboard-reachable **Open in Codex** anchor without a target only when `/api/state` supplies a server-built `codexUrl`. The server SHALL validate a hyphenated UUID before building `codex://threads/<uuid>`. Legacy tasks SHALL qualify only when their ID is present in the configured Desktop title index. Shared eligibility SHALL follow the shared-session-consumer root-identity rule. Other tasks SHALL have no link. The card SHALL refresh when its URL changes, appears or disappears. Covers #108 AC1, AC2, AC3 and AC6.

#### Scenario: Indexed legacy Desktop thread
- **WHEN** a legacy task with a UUID in the configured Desktop index is selected
- **THEN** its detail card has an Open in Codex link to that UUID, reachable by keyboard without horizontal overflow at a narrow viewport
- **AND** activation in the Windows browser opens that thread through the Codex Desktop protocol handler

#### Scenario: Ineligible or changing task
- **WHEN** a task has an unknown or malformed ID, or a subsequent snapshot removes its eligibility
- **THEN** the detail card contains no Open in Codex link
- **AND** a later qualified URL appears without requiring reselection

### Requirement: Navigation preserves read ownership
Activating the link SHALL send no request to the map server and SHALL perform no bridge write, unread acknowledgment, Locate or device request. Selecting in the map SHALL NOT mark a task read. Codex SHALL own marking its thread read, followed by the existing unread reader. The footer and bridge guide SHALL explain this distinction and the guide SHALL describe link eligibility. Covers #108 AC4, AC5 and AC7.

#### Scenario: Open an unread task
- **WHEN** the user opens an unread task through its link
- **THEN** the map makes no action request and does not clear the task itself
- **AND** unread clearing occurs only after the existing reader observes Codex's read evidence
