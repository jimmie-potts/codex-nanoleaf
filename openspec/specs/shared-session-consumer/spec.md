# Shared session consumer

## Purpose

Allow Nanoleaf to consume one shared interpretation of agent sessions while preserving private device ownership, task presentation and reversible source selection.

## Requirements

### Requirement: Explicit source authority
The installation SHALL default to legacy input and persist an explicit legacy/shared selection independently of Work/Quiet/Free. Only the selected input SHALL update each session. Shared mode SHALL use the shared owner as the authority for agent state, with local presentation projections only. This covers #29 source selection and ownership criteria.

#### Scenario: Configure without cutover
- **WHEN** shared input is configured or source software is upgraded
- **THEN** the selected source and device mode remain unchanged

#### Scenario: Cutover and rollback
- **WHEN** the operator selects shared after successful preflight or explicitly returns to legacy
- **THEN** selection commits atomically, prevents duplicate ingestion, preserves preferences and bound assignments/epochs, and survives restart without changing unrelated hooks or installation owner
- **AND** an active comet reservation prevents cutover until it finishes

### Requirement: Validated bounded shared input
The consumer SHALL validate the released versioned snapshot contract and expected owner over authenticated configured numeric-loopback HTTP with bounded time, size and concurrency, no redirects and no proxy use. Source readiness declarations SHALL distinguish operator assertions from verified feed evidence. No provider reducer SHALL be copied to Python. This covers #29 shared-contract, privacy and transport criteria.

#### Scenario: Invalid or unavailable host
- **WHEN** authentication fails, input exceeds bounds, a version/owner/schema is invalid, or a revision regresses
- **THEN** the last valid projection remains with stale/unavailable health and fixed diagnostics, no raw response/credential disclosure and no automatic fallback

#### Scenario: Multiple identities
- **WHEN** concurrent sessions share a project or raw session ID but differ in full source identity
- **THEN** they remain distinct and only explicit bindings connect them to retained local presentation identities

### Requirement: Shared presentation and notices
The consumer SHALL map semantic activity and attention into the existing allocation, split halves, reservations, two-second pulses, single outward waves, comets and mode/scene rules. Nanoleaf SHALL use the shared consumer clear-on-new-turn policy. Acknowledgment, qualified read evidence and work success SHALL remain distinct. This covers #29 notice, rendering and retained-behavior criteria.

#### Scenario: New turn clears previous notice
- **WHEN** the owner evidences a new turn and acknowledges prior notices for the configured Nanoleaf consumer
- **THEN** the consumer stops presenting those notices without inferring readership or success or dismissing other consumers' notices

#### Scenario: Read evidence and explicit acknowledgment
- **WHEN** qualified read evidence is present or an operator acknowledges an exact notice
- **THEN** read evidence suppresses the local blue indicator without writing shared acknowledgment, while an explicit acknowledgment targets only the configured consumer and exact notice with bounded authenticated request identity
- **AND** unavailable read evidence remains unknown and legacy unread clearing remains unchanged

### Requirement: Honest freshness and effect recovery
Disconnected or uncertain shared sessions SHALL keep their last colors steady with no pulses/comets while current peers retain normal behavior. Health SHALL distinguish transport from session evidence freshness. Recovery SHALL preserve epochs and assignments and SHALL NOT replay expired effects. Agents SHALL never wait on this consumer. This covers #29 disconnect and reconnect criteria.

#### Scenario: Feed loss in Work or Free
- **WHEN** a selected shared feed is lost
- **THEN** Work retains steady last colors, notices and assignments, Free remains free of task-light writes, and health reports uncertainty without legacy fallback

#### Scenario: Restart or snapshot resync
- **WHEN** the worker starts or reconnects with a current snapshot after lost changes
- **THEN** current state replaces its projection without replaying old celebrations or restarting retained pulse epochs

### Requirement: Pure sanitized inspection and private ownership
Inspection SHALL report source selection, owner, consumer health and sanitized identity/project mapping without starting a worker, changing state, contacting a device or returning credentials/private metadata. One installation-local Python worker SHALL remain the sole device writer; SQLite SHALL remain private to its operating system. This covers #29 additional health and runtime criteria.

#### Scenario: Inspect integration state
- **WHEN** a caller reads shared status
- **THEN** it receives selected source, neutral identities, connection, last revision/update, evidence age, uncertainty and fixed errors without mutations or credential/path disclosure

### Requirement: Source qualification evidence
The delivery SHALL exercise released fixtures and isolated Linux fake-feed/worker paths, measure bounded consumer overhead, preserve legacy Windows routing where affected, and distinguish source evidence from installed, integrated performance and optical acceptance. This covers #29 verification and performance criteria.

#### Scenario: Consumer qualification
- **WHEN** source acceptance is evaluated
- **THEN** repeatable synthetic profiles and failure/recovery tests demonstrate bounded resources and preserved behavior without personal hooks, agents or devices
