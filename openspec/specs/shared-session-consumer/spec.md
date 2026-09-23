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
The consumer SHALL map semantic activity and attention into the existing allocation, split halves, reservations, two-second pulses, single outward waves, comets and mode/scene rules. Nanoleaf SHALL use the shared consumer clear-on-new-turn policy. Acknowledgment, qualified read evidence and work success SHALL remain distinct. A session with an evidenced parent SHALL be presented as part of its nearest top-level ancestor's task, contributing its attention and owner-counted fresh activity but not its notices. A group whose topmost member in the snapshot has a missing parent, or whose parents form a cycle, SHALL be presented only while it has blocked or question attention, keyed by that member or by the cycle's smallest key. This covers #29 notice, rendering and retained-behavior criteria and #74 subagent presentation.

#### Scenario: New turn clears previous notice
- **WHEN** the owner evidences a new turn and acknowledges prior notices for the configured Nanoleaf consumer
- **THEN** the consumer stops presenting those notices without inferring readership or success or dismissing other consumers' notices

#### Scenario: Read evidence and explicit acknowledgment
- **WHEN** qualified read evidence is present or an operator acknowledges an exact notice
- **THEN** read evidence suppresses the local blue indicator without writing shared acknowledgment, while an explicit acknowledgment targets only the configured consumer and exact notice with bounded authenticated request identity
- **AND** unavailable read evidence remains unknown and legacy unread clearing remains unchanged

#### Scenario: Subagent sessions join their parent task
- **WHEN** the snapshot contains child sessions of a top-level session, including children with retained unknown-turn notices
- **THEN** only the top-level task appears in the map count and allocation, its status reflects its own notices plus child blocked/question attention and owner-counted fresh child activity, and child notices neither make it unread nor queue comets

#### Scenario: Earlier child tasks leave
- **WHEN** a snapshot arrives while child sessions retain rows and Lines from the earlier projection
- **THEN** those child tasks leave the count and release their Lines to waiting tasks without changing other tasks' slots, epochs or preferences, modes, scenes or device state

#### Scenario: Child without its parent
- **WHEN** the topmost ancestor of a child that is present in the snapshot has a missing parent
- **THEN** that group is presented under the topmost present member, whatever the snapshot order, while it has blocked or question attention, and is otherwise not a task

### Requirement: Honest freshness and effect recovery
Disconnected or uncertain shared sessions SHALL keep their last colors steady with no pulses/comets while current peers retain normal behavior. A task SHALL be current only when current evidence from one of its members supplies its displayed status. When current members that supplied a retained status no longer supply it, the task SHALL take its new status while remaining uncertain and steady. A subagent alert of higher priority than the retained status SHALL be shown steadily rather than hidden. Working SHALL follow the owner's count of fresh active children, which excludes uncertain children. A later authoritative owner revision that removes an unknown-ID approval on the same turn MAY clear that frozen blocked color while preserving uncertain evidence, assignments and effect suppression. Health and map task status evidence SHALL distinguish transport and session freshness from the displayed status. Recovery SHALL preserve epochs and assignments and SHALL NOT replay expired effects. Agents SHALL never wait on this consumer. This covers #29 disconnect and reconnect criteria, #72 approval recovery and #74 subagent freshness.

#### Scenario: Feed loss in Work or Free
- **WHEN** a selected shared feed is lost
- **THEN** Work retains steady last colors, notices and assignments, Free remains free of task-light writes, and health reports uncertainty without legacy fallback

#### Scenario: Restart or snapshot resync
- **WHEN** the worker starts or reconnects with a current snapshot after lost changes
- **THEN** current state replaces its projection without replaying old celebrations or restarting retained pulse epochs

#### Scenario: Owner retires one uncertain approval
- **WHEN** a later validated owner revision removes an unknown-ID approval from the same turn while that session remains uncertain
- **THEN** the consumer clears frozen blocked red, marks task status evidence uncertain, and does not pulse, replay a comet or change assignments and notices

#### Scenario: Current subagent alert under an uncertain parent
- **WHEN** a top-level session is uncertain and a current child reports blocked or question attention
- **THEN** the task shows that alert with current status evidence, and when that current child resolves it the task takes its new status with uncertain evidence and no pulse

#### Scenario: Uncertain subagent alert
- **WHEN** only uncertain children supply a task's blocked or question attention, including under a current parent
- **THEN** the task shows the alert steadily with uncertain status evidence and no new outward wave, including over a retained lower status or a current question

#### Scenario: Silent subagent
- **WHEN** a subagent that supplied its task's working status becomes uncertain while its parent is current
- **THEN** the task follows the parent's current evidence and the owner's active count, which no longer includes that subagent, so the parent's idle state, turns and completions show normally
- **AND** when the parent is uncertain too, the task keeps its last color steadily

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
