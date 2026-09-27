## ADDED Requirements

### Requirement: Named synthetic scenarios

The demo SHALL seed a named scenario into an empty, caller-owned state directory: the Lines and Light Panels registry and fixture layouts, synthetic projects and tasks, and the hook waits behind blocked and question tasks. The `reference` scenario SHALL match the browser suite's fixture. `layout-unavailable` SHALL save Line positions without drawing geometry. Seeding SHALL be deterministic for a fixed clock and SHALL refuse an unknown scenario or a non-empty directory without writing. (Issue #193: fresh documented runs cover Lines and Panels.)

#### Scenario: Reference seed
- **WHEN** `reference` is seeded
- **THEN** five tasks in all four statuses are placed on both devices, task-1 waits on a shell approval and task-2 on an asynchronous question

#### Scenario: Refused seed
- **WHEN** the scenario is unknown or the directory already holds state
- **THEN** seeding fails and the directory is unchanged

### Requirement: Served run on its own port and state

`demo.py serve` SHALL start the wall server as the installed map starts, over the given state directory, bound to `127.0.0.1` on the requested port, where 0 lets the kernel choose. It SHALL write `map-server.json` with its port and instance, print one ready line with its URL and instance, never print the page's edit token, and exit on SIGTERM leaving the directory to its owner. (Issue #193: two runs share nothing.)

#### Scenario: Ready run
- **WHEN** a seeded directory is served on port 0
- **THEN** the ready line names a loopback URL whose `/health` reports the same instance, and the map page and state answer from that directory

#### Scenario: Relaunch after a reseed
- **WHEN** the directory is emptied, reseeded and served on the recorded port
- **THEN** the run answers on the same port with the new scenario's state

#### Scenario: Independent runs
- **WHEN** two runs serve at once and one is driven
- **THEN** they use different ports and the other run's state is unchanged

### Requirement: Device boundary

Every demo entry point SHALL, before running bridge code, refuse outbound socket connections, datagram sends and new processes, and SHALL route the wall server's light-request seam to a trap. Each refusal SHALL be appended to the run's `device-boundary.jsonl` with its kind, target and time and SHALL NOT include a credential. The wall server SHALL treat a refusal as an unreachable device. (Issue #193: device-request traps fail on attempted physical requests.)

#### Scenario: Attempted physical and service requests
- **WHEN** a guarded process calls the Nanoleaf transport, the worker launcher or a loopback service
- **THEN** each attempt fails as a boundary refusal, is recorded, and the service receives no connection, while an unguarded control process does connect

#### Scenario: A path that bypasses the seam
- **WHEN** a guarded map geometry read uses the default transport
- **THEN** its socket connection is refused and recorded

#### Scenario: Served map without saved geometry
- **WHEN** `layout-unavailable` is served
- **THEN** its startup layout read is recorded as a refused light request, the map reports the unavailable layout and the server keeps serving

### Requirement: Driven task transitions

`demo.py drive` SHALL apply a named transition's hook events through the actual hook handler and the worker stand-in, and SHALL refuse an unknown transition without changing state. Transitions marked as defects SHALL be known-wrong inputs. (Issue #193: task transitions.)

#### Scenario: Completion
- **WHEN** `complete` is driven on `reference`
- **THEN** task-0 becomes unread on the same Line and each device in Work queues its completion comet

#### Scenario: Defect transitions
- **WHEN** `defect-approve-other-tool` or `defect-complete-stale-turn` is driven
- **THEN** task-1 stays blocked and task-0 stays working

### Requirement: Assertion-backed capture steps

The wall plug-in SHALL define capture steps for the Lines wall, a task completion, an approval, the Project layout configuration, the lighting modes and assembly replay, the Light Panels and the refused device read. Each step SHALL record named assertions on the page's painted colors, listed statuses, alerts or renderer state, and SHALL assert that the page requested only its run origin and that the run recorded no device attempt, except the refused-read step, which requires its attempt to be refused. (Issue #193: presentation, configuration and animation states; screenshot and video.)

#### Scenario: Reference steps
- **WHEN** each reference step runs on a freshly seeded run
- **THEN** every assertion passes and a screenshot and a finalized video exist

### Requirement: Negative controls fail

The plug-in SHALL define negative controls that apply a known-wrong transition or serve a known-wrong page to the same assertions. Each control SHALL fail at its named assertion rather than crash. A presentation control SHALL first assert that its page change was applied exactly once. (Issue #193: a known defect is detected and reference behavior passes.)

#### Scenario: Stale completion
- **WHEN** `control-stale-completion` runs
- **THEN** the capture fails at "task-0 reads unread in the task list"

#### Scenario: Unread painted as working
- **WHEN** `control-unread-painted-working` runs
- **THEN** the capture fails at "task-0's Line is painted in the unread color"

#### Scenario: Stale red
- **WHEN** `control-stale-red` runs
- **THEN** the capture fails at "task-1 reads working in the task list"

### Requirement: Labelled components and boundary check

The plug-in SHALL label the wall server, page, state store, hook handler and allocation as actual, and the light worker, both devices and the Codex metadata as simulated. Its start-time `device-boundary` check SHALL fail when any recorded attempt was not refused, when a scenario other than `layout-unavailable` recorded an attempt during start, or when `layout-unavailable` recorded no refused light request. Its readiness probe SHALL fail for an installed service port or a map instance other than the run's own. (Issue #193: identify real and simulated components.)

#### Scenario: Another map on the port
- **WHEN** the run's receipt names an instance that `/health` does not report
- **THEN** the probe fails with the reason that health names another map instance
