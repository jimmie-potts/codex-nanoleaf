# Shared session consumer

## Purpose

Allow Nanoleaf to consume one shared interpretation of agent sessions while preserving private device ownership, task presentation and reversible source selection.

## Requirements

### Requirement: Explicit source authority
The installation SHALL default to legacy input and persist an explicit legacy/shared selection independently of Work/Quiet/Free. Only the selected input SHALL update each session. Shared mode SHALL use the shared owner as the authority for agent state, with local presentation projections only. The operator SHALL register this integration's hooks for every legacy event in the selected Codex home before selecting legacy input. This covers #29 source selection and ownership criteria and #89 rollback safety.

#### Scenario: Configure without cutover
- **WHEN** shared input is configured or source software is upgraded
- **THEN** the selected source and device mode remain unchanged

#### Scenario: Cutover and rollback
- **WHEN** the operator selects shared after successful preflight or explicitly returns to legacy with the integration's hooks registered
- **THEN** selection commits atomically, prevents duplicate ingestion, preserves preferences and bound assignments/epochs, and survives restart without changing unrelated hooks or installation owner
- **AND** an active comet reservation prevents cutover until it finishes

#### Scenario: Legacy selection without registered hooks
- **WHEN** the operator selects legacy while the selected Codex home lacks this integration's marked handler for any legacy event
- **THEN** selection is refused without changing source state and the diagnostic names `hooks register`

### Requirement: Explicit legacy hook lifecycle
The CLI SHALL provide hook removal and registration commands that take a Codex home explicitly and change only handlers marked `nanoleaf-codex-status-v1`. Removal SHALL create a private backup, preserve every other hook entry, and SHALL NOT change device modes, tasks or device state. Repeating either operation SHALL be safe. Removal SHALL be refused while legacy input is selected. Malformed hook JSON SHALL be left untouched. Registration SHALL preserve existing or backed-up commands, fill missing legacy events, and include the selected installation state directory in newly generated commands. Hook-file replacement SHALL be atomic.

#### Scenario: Remove and restore marked hooks
- **WHEN** an operator removes legacy hooks after selecting shared input and then registers them for rollback
- **THEN** only marked handlers are removed and restored, unrelated entries remain unchanged, a backup exists, and repeating either operation leaves the configuration valid and equivalent

#### Scenario: Refuse removal during legacy input
- **WHEN** the operator removes hooks while legacy input is selected
- **THEN** the command refuses without modifying the Codex home or Nanoleaf state

#### Scenario: Malformed hook configuration
- **WHEN** a hook lifecycle command reads malformed `hooks.json`
- **THEN** it reports failure and leaves the original file byte-for-byte unchanged

### Requirement: Validated bounded shared input
The consumer SHALL request snapshot 1.1, require a non-negative safe integer generation no greater than its revision for every session, and validate the versioned snapshot contract and expected owner over authenticated configured numeric-loopback HTTP with bounded time, size and concurrency, no redirects and no proxy use. Source readiness declarations SHALL distinguish operator assertions from verified feed evidence. No provider reducer SHALL be copied to Python. A session whose provider, client, host and source are not declared in the configuration SHALL be skipped rather than rejecting the snapshot: it SHALL receive no Line, wave, comet or acknowledgment and SHALL take no part in parent and subagent grouping, while declared sessions keep updating. This covers #29 shared-contract, privacy and transport criteria and #111 undeclared sources.

#### Scenario: Invalid or unavailable host
- **WHEN** authentication fails, input exceeds bounds, a version/owner/schema is invalid, or a revision regresses
- **THEN** the last valid projection remains with stale/unavailable health and fixed diagnostics, no raw response/credential disclosure and no automatic fallback

#### Scenario: Multiple identities
- **WHEN** concurrent sessions share a project or raw session ID but differ in full source identity
- **THEN** they remain distinct and only explicit bindings connect them to retained local presentation identities
- **AND** Codex sessions may resolve local title and project metadata by provider and raw session ID without merging identities or creating lifecycle state

#### Scenario: Undeclared source among declared sessions
- **WHEN** a valid snapshot contains sessions from a source missing from the declared sources alongside declared sessions
- **THEN** only the declared sessions are presented and keep updating, and the connection stays current
- **AND** a snapshot containing only undeclared sessions leaves the wall without shared tasks and the connection current

#### Scenario: Undeclared parent of a declared subagent
- **WHEN** a declared session's evidenced parent is skipped
- **THEN** the declared session follows the existing missing-parent rule and a skipped session never contributes to a declared task

#### Scenario: Source declared later
- **WHEN** the operator declares a source whose sessions already exist in the feed and selects shared input again
- **THEN** those sessions appear in their current state without replaying earlier outward waves or completion comets

### Requirement: Shared presentation and notices
The consumer SHALL map semantic activity and attention into the existing allocation, split halves, reservations, two-second pulses, single outward waves, comets and mode/scene rules. Nanoleaf SHALL use the shared consumer clear-on-new-turn policy. Acknowledgment, qualified read evidence and work success SHALL remain distinct. A session with an evidenced parent SHALL be presented as part of its nearest top-level ancestor's task, contributing its attention and owner-counted fresh activity but not its notices. A group whose topmost member in the snapshot has a missing parent, or whose parents form a cycle, SHALL be presented only while it has blocked or question attention, keyed by that member or by the cycle's smallest key. This covers #29 notice, rendering and retained-behavior criteria and #74 subagent presentation.

#### Scenario: New turn clears previous notice
- **WHEN** the owner evidences a new turn and acknowledges prior notices for the configured Nanoleaf consumer
- **THEN** the consumer stops presenting those notices without inferring readership or success or dismissing other consumers' notices

#### Scenario: Read evidence and explicit acknowledgment
- **WHEN** qualified read evidence is present or an operator acknowledges an exact notice
- **THEN** read evidence ends the local unread pulse and retains the idle task and Line without writing shared acknowledgment, while an explicit acknowledgment targets only the configured consumer and exact notice with bounded authenticated request identity
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
Disconnected or uncertain shared sessions SHALL keep their last colors steady with no pulses/comets while current peers retain normal behavior. A task SHALL be current only when current evidence from one of its members supplies its displayed status. When current members that supplied a retained status no longer supply it, the task SHALL take its new status while remaining uncertain and steady. A subagent alert of higher priority than the retained status SHALL be shown steadily rather than hidden. Working SHALL follow the owner's count of fresh active children, which excludes uncertain children. A later authoritative owner revision that removes an unknown-ID approval on the same turn MAY clear that frozen blocked color while preserving uncertain evidence, assignments and effect suppression. A retained unread task SHALL become idle, steadily and with uncertain evidence, when the owner reports its session read or every notice acknowledged for this consumer, even while its session evidence is uncertain; no other retained status SHALL change from uncertain evidence. Health and map task status evidence SHALL distinguish transport and session freshness from the displayed status. Recovery SHALL preserve epochs and assignments and SHALL NOT replay expired effects. Agents SHALL never wait on this consumer. This covers #29 disconnect and reconnect criteria, #72 approval recovery, #74 subagent freshness and #88 stale read evidence.

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
- **THEN** the task follows the parent's current evidence and the owner's active count, which no longer includes that subagent, so the parent's idle state, turns and completion status show normally; a completion whose unread transition an active subagent delayed shows without a completion comet (#81)
- **AND** when the parent is uncertain too, the task keeps its last color steadily until current evidence from the members that supplied it, including that subagent, clears it

#### Scenario: Stale unread task read or acknowledged
- **WHEN** a task retains unread while its session is uncertain and the owner reports the session read, or every notice acknowledged for this consumer
- **THEN** the task becomes idle without a pulse, outward wave or comet, and its row and assigned Line remain until authoritative removal or device-local eviction

#### Scenario: Other stale changes stay frozen
- **WHEN** an uncertain session's retained status is working, question or blocked, or a retained unread session's uncertain evidence would show another status, or only some notices are acknowledged
- **THEN** the task keeps its retained status steadily

### Requirement: Pure sanitized inspection and private ownership
Inspection SHALL report source selection, owner, consumer health and sanitized identity/project mapping without starting a worker, changing state, contacting a device or returning credentials/private metadata. Inspection SHALL also report how many sessions the last projection skipped and their distinct source identities. One installation-local Python worker SHALL remain the sole device writer; SQLite SHALL remain private to its operating system. This covers #29 additional health and runtime criteria and #111 skipped-source visibility.

#### Scenario: Inspect integration state
- **WHEN** a caller reads shared status
- **THEN** it receives selected source, neutral identities, connection, last revision/update, evidence age, uncertainty and fixed errors without mutations or credential/path disclosure

#### Scenario: Inspect skipped sources
- **WHEN** the last projection skipped sessions from undeclared sources
- **THEN** shared status reports the skipped session count and each distinct skipped source identity, so a missing declaration is visible

### Requirement: Source qualification evidence
The delivery SHALL exercise released fixtures and isolated Linux fake-feed/worker paths, measure bounded consumer overhead, and distinguish source evidence from installed, integrated performance and optical acceptance. This covers #29 verification and performance criteria; the legacy Windows routing clause was retired under [issue #131](https://github.com/jimmie-potts/codex-nanoleaf/issues/131).

#### Scenario: Consumer qualification
- **WHEN** source acceptance is evaluated
- **THEN** repeatable synthetic profiles and failure/recovery tests demonstrate bounded resources and preserved behavior without personal hooks, agents or devices

### Requirement: Wall links use the presented root identity
The wall task projection SHALL expose `codexUrl` only when its presented root session has provider `codex`, client `desktop` and a valid UUID session ID. Folded children SHALL NOT supply or replace that identity. The URL SHALL be built on the server and SHALL NOT enter controller or integration API projections or the shared feed. Eligibility SHALL NOT change session lifecycle, allocation or read state. Covers #108 AC2, AC3, AC4 and AC5.

#### Scenario: Desktop parent with folded child
- **WHEN** a shared Desktop root session has a folded child
- **THEN** its single wall task links to the parent's UUID, never the child's

#### Scenario: Ineligible root
- **WHEN** a root is Codex CLI, Claude Code, an unknown client, or has a malformed session ID
- **THEN** its wall task has no link even if a child is an eligible Desktop session or a matching ID exists in the local title index

### Requirement: Authoritative session retirement
A current owner snapshot that removes a task SHALL remove its task-specific local presentation and release its Lines through the existing allocator. A changed generation for a retained identity SHALL have the same reset effect before projecting the new task. The consumer SHALL preserve unrelated tasks, the global project catalogue, project colors and reservations, preferences, source selection, modes and scenes. Retirement SHALL NOT acknowledge a notice, mark work successful or terminate an agent.

#### Scenario: Removal and empty idle
- **WHEN** the current owner removes a parent and its known descendants, including when the consumer reconnects to an empty snapshot
- **THEN** their tasks and task-specific overrides disappear, their assignments become available, and normal idle behavior applies with no replayed effects

#### Scenario: Missed removal and same-identity recreation
- **WHEN** a later current snapshot has a different generation for a retained identity, including after a consumer restart
- **THEN** the task starts with fresh local defaults and does not reuse its old manual project, assignment or task effects
- **AND** tasks with unchanged generations retain their existing presentation continuity

#### Scenario: Unavailable is not removal
- **WHEN** the feed is unavailable or fails validation
- **THEN** the consumer preserves its last valid projection with unavailable health and does not infer retirement

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
