## MODIFIED Requirements

### Requirement: Shared task visibility and local eviction
Shared root tasks SHALL retain their wall row and allocation eligibility while the owner retains them, including after read or acknowledgment changes them to idle. Idle Lines SHALL be steady in the task-light palette's Base color with no new wave or completion comet. The existing orphan-child rule and legacy presentation policy SHALL remain unchanged. The selected task details SHALL offer a same-origin protected Evict action that removes the task's row, assignment and task effects from the current device only. Eviction SHALL NOT change the owner record, conversation, read evidence, notices, modes, global preferences, peers or other devices. The UI SHALL state the local scope. This refines Hub #218's presentation acceptance following the installed trial.

#### Scenario: Read without retirement
- **WHEN** an unread shared root becomes read or acknowledged while the owner retains it
- **THEN** its row and assigned Line remain, its unread pulse ends, and no new wave or comet starts
- **AND** authoritative removal later releases its row and Line normally

#### Scenario: Persistent device-local eviction
- **WHEN** the operator evicts a selected shared task
- **THEN** its row and allocation disappear on this device and remain suppressed across polling, read changes, feed failure/recovery and process restart
- **AND** its owner record and other devices are unchanged, so it still counts toward future owner-based Work/Free automation

#### Scenario: New work and stale controls
- **WHEN** a new identifiable turn or generation replaces the evicted one
- **THEN** it becomes eligible for a fresh allocation without replaying prior effects
- **AND** an eviction submitted from details for an older turn, generation or source selection is rejected without changing the current task

#### Scenario: Unknown turn and legacy input
- **WHEN** no changed turn identity or generation is evidenced
- **THEN** refresh, elapsed time and read evidence alone do not re-admit an evicted task
- **AND** legacy tasks do not offer this shared-input eviction action
