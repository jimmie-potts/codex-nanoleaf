## MODIFIED Requirements

### Requirement: Explicit source authority
The installation SHALL default to legacy input and persist an explicit legacy/shared selection independently of Work/Quiet/Free. Only the selected input SHALL update each session. Shared mode SHALL use the shared owner as the authority for agent state, with local presentation projections only. The operator SHALL register this integration's legacy hooks in the selected Codex home before selecting legacy input. This covers #29 source selection and ownership criteria and #89 rollback safety.

#### Scenario: Configure without cutover
- **WHEN** shared input is configured or source software is upgraded
- **THEN** the selected source and device mode remain unchanged

#### Scenario: Cutover and rollback
- **WHEN** the operator selects shared after successful preflight or explicitly returns to legacy with the integration's hooks registered
- **THEN** selection commits atomically, prevents duplicate ingestion, preserves preferences and bound assignments/epochs, and survives restart without changing unrelated hooks or installation owner
- **AND** an active comet reservation prevents cutover until it finishes

#### Scenario: Legacy selection without registered hooks
- **WHEN** the operator selects legacy while the selected Codex home lacks this integration's marked hooks
- **THEN** selection is refused without changing source state and the diagnostic names `hooks register`

## ADDED Requirements

### Requirement: Explicit legacy hook lifecycle
The CLI SHALL provide hook removal and registration commands that take a Codex home explicitly and change only handlers marked `nanoleaf-codex-status-v1`. Removal SHALL create a private backup, preserve every other hook entry, and SHALL NOT change device modes, tasks or device state. Repeating either operation SHALL be safe. Removal SHALL be refused while shared input is selected. Malformed hook JSON SHALL be left untouched.

#### Scenario: Remove and restore marked hooks
- **WHEN** an operator removes and then registers legacy hooks for a Codex home
- **THEN** only marked handlers are removed and restored, unrelated entries remain unchanged, a backup exists, and repeating either operation leaves the configuration valid and equivalent

#### Scenario: Refuse removal during shared input
- **WHEN** the operator removes hooks while shared input is selected
- **THEN** the command refuses without modifying the Codex home or Nanoleaf state

#### Scenario: Malformed hook configuration
- **WHEN** a hook lifecycle command reads malformed `hooks.json`
- **THEN** it reports failure and leaves the original file byte-for-byte unchanged
