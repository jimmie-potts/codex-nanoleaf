## MODIFIED Requirements

### Requirement: Shared presentation and notices
The consumer SHALL map semantic activity and attention into the existing allocation, split halves, reservations, two-second pulses, single outward waves, comets and mode/scene rules. Nanoleaf SHALL use the shared consumer clear-on-new-turn policy. Acknowledgment, qualified read evidence and work success SHALL remain distinct. A session with an evidenced parent SHALL be presented as part of its nearest top-level ancestor's task, contributing its attention and owner-counted fresh activity but not its notices. A child whose ancestor is absent from the snapshot SHALL be presented alone and only while it has blocked or question attention. This covers #29 notice, rendering and retained-behavior criteria and #74 subagent presentation.

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
- **WHEN** a child session's ancestor is absent from the snapshot
- **THEN** the child is presented alone while it has blocked or question attention and is otherwise not a task

### Requirement: Honest freshness and effect recovery
Disconnected or uncertain shared sessions SHALL keep their last colors steady with no pulses/comets while current peers retain normal behavior. A task SHALL be current only when current evidence from one of its members supplies its displayed status. When current members that supplied a retained status no longer supply it, the task SHALL take its new status while remaining uncertain and steady, and a subagent alert SHALL be shown steadily rather than hidden behind a retained non-alert color. A later authoritative owner revision that removes an unknown-ID approval on the same turn MAY clear that frozen blocked color while preserving uncertain evidence, assignments and effect suppression. Health and map task status evidence SHALL distinguish transport and session freshness from the displayed status. Recovery SHALL preserve epochs and assignments and SHALL NOT replay expired effects. Agents SHALL never wait on this consumer. This covers #29 disconnect and reconnect criteria, #72 approval recovery and #74 subagent freshness.

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
- **THEN** the task shows the alert steadily with uncertain status evidence and no new outward wave
