## MODIFIED Requirements

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
- **THEN** the task becomes idle without a pulse, outward wave or comet, and its Line becomes available to a waiting task

#### Scenario: Other stale changes stay frozen
- **WHEN** an uncertain session's retained status is working, question or blocked, or a retained unread session's uncertain evidence would show another status, or only some notices are acknowledged
- **THEN** the task keeps its retained status steadily
