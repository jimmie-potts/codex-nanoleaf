# wall-verification-runs Specification

## Purpose
Lets an agent start the actual wall server over named synthetic state as a disposable, leased run of the shared app verification core, drive task transitions and the page, keep assertion-backed proof and hand over a preview, while a process boundary refuses and records every device, service and process request. A hub-paired run also follows a paired Hub run's feed and serves the controller API that Hub calls, and its boundary allows only that Hub's loopback port. A run proves no physical output.

## Requirements

### Requirement: Named synthetic scenarios

The demo SHALL seed a named scenario into an empty, caller-owned state directory: the Lines and Light Panels registry and fixture layouts, synthetic projects and tasks, and the hook waits behind blocked and question tasks. It SHALL mark the directory with `demo-run.json` naming the scenario. The `reference` scenario SHALL match the browser suite's fixture. `layout-unavailable` SHALL save Line positions without drawing geometry. Seeding SHALL be deterministic for a fixed clock and SHALL refuse an unknown scenario, a non-empty directory, or the installation's state directory or a directory inside it, without writing; `demo.py seed` SHALL exit with status 2 for the installation's state directory. (Issue #193: fresh documented runs cover Lines and Panels.)

#### Scenario: Reference seed
- **WHEN** `reference` is seeded
- **THEN** five tasks in all four statuses are placed on both devices, task-1 waits on a shell approval and task-2 on an asynchronous question

#### Scenario: Refused seed
- **WHEN** the scenario is unknown or the directory already holds state
- **THEN** seeding fails and the directory is unchanged

#### Scenario: Marked directory
- **WHEN** a scenario is seeded
- **THEN** the directory holds `demo-run.json` naming that scenario

#### Scenario: Seed refuses the installation's state
- **WHEN** `demo.py seed` is given the installation's state directory, or a directory inside it, under the user's home
- **THEN** it exits with status 2 without a traceback and writes nothing

### Requirement: Served run on its own port and state

`demo.py serve` SHALL start the wall server as the installed map starts, including its bounded layout retries, over the given state directory, bound to `127.0.0.1` on the requested port, where 0 lets the kernel choose. It SHALL write `map-server.json` with its port and instance, print one ready line with its URL and instance, never print the page's edit token, and exit on SIGTERM leaving the directory to its owner. `serve` and `drive` SHALL refuse, with exit status 2 and without writing, a directory that `seed` did not mark and the installation's state directory or a directory inside it. (Issue #193: two runs share nothing.)

#### Scenario: Ready run
- **WHEN** a seeded directory is served on port 0
- **THEN** the ready line names a loopback URL whose `/health` reports the same instance, and the map page and state answer from that directory

#### Scenario: Relaunch after a reseed
- **WHEN** the directory is emptied, reseeded and served on the recorded port
- **THEN** the run answers on the same port with the new scenario's state

#### Scenario: Independent runs
- **WHEN** two runs serve at once and one is driven
- **THEN** they use different ports and the other run's state is unchanged

#### Scenario: Refused state directory
- **WHEN** `serve` or `drive` is given an unmarked directory, or the installation's state directory under the user's home
- **THEN** it exits with status 2, and neither the directory's state nor its `map-server.json` changes

### Requirement: Device boundary

Every demo entry point SHALL, before calling any bridge function, refuse outbound socket connections, datagram sends, new processes (the audited process events and the unaudited launcher that multiprocessing's spawn and forkserver use), foreign libraries and symbols loaded through ctypes, on Python 3.14 any foreign call through ctypes, and new subinterpreters, and SHALL route the wall server's light-request seam to a trap. Each refusal SHALL be appended to the run's `device-boundary.jsonl` with its kind, target and time and SHALL NOT include a credential. The wall server SHALL treat a refusal as an unreachable device. (Issue #193: device-request traps fail on attempted physical requests.)

#### Scenario: Attempted physical and service requests
- **WHEN** a guarded process calls the Nanoleaf transport, the worker launcher or a loopback service
- **THEN** each attempt fails as a boundary refusal, is recorded, and the service receives no connection, while an unguarded control process does connect

#### Scenario: A path that bypasses the seam
- **WHEN** a guarded map geometry read uses the default transport
- **THEN** its socket connection is refused and recorded

#### Scenario: Served map without saved geometry
- **WHEN** `layout-unavailable` is served
- **THEN** its startup layout read is recorded as a refused light request, the map reports the unavailable layout and the server keeps serving

#### Scenario: Paths without a socket or process audit event
- **WHEN** a guarded process starts a multiprocessing spawn child, loads a library or looks up a symbol through ctypes, on Python 3.14 calls a foreign function resolved before the boundary, or creates a subinterpreter where Python provides one
- **THEN** each attempt is refused and recorded and the service receives no connection, while an unguarded control process reaches it by each path

### Requirement: Driven task transitions

`demo.py drive` SHALL apply a named transition's hook events through the actual hook handler and the worker stand-in, and SHALL refuse an unknown transition without changing state. Transitions marked as defects SHALL be known-wrong inputs or a known-wrong stand-in that tries to send the effect to each device. (Issue #193: task transitions.)

#### Scenario: Completion
- **WHEN** `complete` is driven on `reference`
- **THEN** task-0 becomes unread on the same Line and each device in Work queues its completion comet

#### Scenario: Defect transitions
- **WHEN** `defect-approve-other-tool` or `defect-complete-stale-turn` is driven
- **THEN** task-1 stays blocked and task-0 stays working

#### Scenario: A stand-in that contacts the devices
- **WHEN** `defect-complete-contacts-device` is driven
- **THEN** task-0 becomes unread, and the stand-in's effect request to each device is refused and recorded

### Requirement: Assertion-backed capture steps

The wall plug-in SHALL define capture steps for the Lines wall, a task completion, an approval, an approval request, a resumed task, the Project layout configuration, the lighting modes with assembly replay and reduced motion, the Light Panels and the refused device read. Each step SHALL record named assertions on the page's painted colors, listed statuses, alerts or renderer state. It SHALL assert that the page requested only its run origin and that the run recorded no device attempt during the step. The refused-read step instead SHALL require its startup layout read to have been refused, and SHALL accept during the step only the map's bounded layout retries: `GET` requests for the whole layout of `192.0.2.1`, at most three since the seed, each recorded at least 9.9 s after the previous one. Every step SHALL be fresh, so the core reseeds its scenario and relaunches the wall on the same port before it runs. (Issue #193: presentation, configuration and animation states; screenshot and video.)

#### Scenario: Reference steps
- **WHEN** each reference step runs through the core's capture driver
- **THEN** every assertion passes and a screenshot and a finalized video exist

#### Scenario: Transition keeps its Line
- **WHEN** a transition step drives `complete`, `approve`, `request-approval` or `resume`
- **THEN** the task is listed in its new status on the same Line, that Line is painted in the new status color, every other Line keeps its colors and the alerts match the new state

#### Scenario: A predicate check sees a wrong observation
- **WHEN** a step's check resolves `false`, or returns a value other than `true`, instead of throwing
- **THEN** the capture fails at that assertion

#### Scenario: Reduced motion
- **WHEN** the lighting-modes step switches the page to reduced motion in Work
- **THEN** the light phase holds still and Replay does not animate

#### Scenario: The map retries its layout read during the refused-read step
- **WHEN** the refused-read step starts 10 s or more after the wall, so the map retries its layout read during the step
- **THEN** the step passes, and any other device attempt would fail it

#### Scenario: A map that reads its layout on every poll
- **WHEN** the wall reads its layout on every poll and the refused-read step runs
- **THEN** the capture fails at "the only device attempts during the step are the map's bounded layout reads"

### Requirement: Negative controls fail

The plug-in SHALL define negative controls that apply a known-wrong transition, serve a known-wrong page, or use a stand-in that contacts the devices, to the same assertions. Each control SHALL fail at its named assertion rather than crash. A presentation control SHALL first assert that its page change was applied exactly once. (Issue #193: a known defect is detected and reference behavior passes.)

#### Scenario: Stale completion
- **WHEN** `control-stale-completion` runs
- **THEN** the capture fails at "task-0 reads unread in the task list"

#### Scenario: Unread painted as working
- **WHEN** `control-unread-painted-working` runs
- **THEN** the capture fails at "task-0's Line is painted in the unread color"

#### Scenario: Stale red
- **WHEN** `control-stale-red` runs
- **THEN** the capture fails at "task-1 reads working in the task list"

#### Scenario: Device attempt during a step
- **WHEN** `control-device-attempt` runs
- **THEN** the capture fails at "no device attempt was recorded during the step", and its boundary record lists both refused effect requests

### Requirement: Labelled components and boundary check

The plug-in SHALL label the wall server, page, state store, hook handler and allocation as actual, and the light worker, both devices and the Codex metadata as simulated. Its `device-boundary` check SHALL run at start and in `doctor`. It SHALL fail when a scenario other than `layout-unavailable` recorded any attempt since its last seed. For `layout-unavailable` it SHALL fail when the log holds anything other than the map's layout reads of the Lines, `GET` requests for the whole layout of `192.0.2.1`, when it holds none, or when it holds more than three or two recorded less than 9.9 s apart. Its readiness probe SHALL fail for an installed service port or a map instance other than the run's own. A failed start SHALL be named from the server's stderr by a fixed cause line or the Python exception type alone, never an exception message, and a failed seed SHALL be named `demo.py seed failed: <cause>` from the same mapping, never with the command or its paths. Each capture, including a failed one, SHALL attach the boundary record of its step. (Issue #193: identify real and simulated components.)

#### Scenario: Another map on the port
- **WHEN** the run's receipt names an instance that `/health` does not report
- **THEN** the probe fails with the reason that health names another map instance

#### Scenario: Unexpected attempts in layout-unavailable
- **WHEN** a `layout-unavailable` run's log holds a process, socket or other light request beside the layout read
- **THEN** the device-boundary check fails

#### Scenario: A failed capture keeps its boundary record
- **WHEN** a capture fails at an earlier assertion
- **THEN** its capture still holds `device-boundary.json` for its step

#### Scenario: A failed seed
- **WHEN** `demo.py seed` fails during `start` with a Python error
- **THEN** `failure.detail` names the fixed cause, and neither the command, the interpreter path nor the checkout path appears in the result, the receipt or the events

### Requirement: Supervised runs through the shared core

`npm run verify -- <operation>` SHALL run the shared core's operations with the wall plug-in, named `wall`, whose default scenario is `reference`. The receipt SHALL name the checkout's revision and dirty flag and a digest of the page and its three Prism assets. A run SHALL start only after its ready line, its probe and its device-boundary check pass. The repository SHALL check the supervised lifecycle against real transient user units where a user manager exists, and SHALL skip with the reason printed where none exists. (Issue #193: two runs share nothing; failed starts and expired leases clean only owned resources; a handoff is reproducible after expiry without modifying retained proof.)

#### Scenario: Run, proof and cleanup
- **WHEN** a run starts, captures, hands off with a reset, captures again, extends and stops
- **THEN** the receipt validates, doctor reads it running with a passing probe and a matching artifact, the verified set keeps its checksums through the later capture and the extension, and stop removes the unit, lease timer and runtime directory

#### Scenario: A start that attempts a device request
- **WHEN** the served state makes the wall ask a device for its layout during a `reference` start
- **THEN** the device-boundary check fails the start and the start leaves no unit, timer or runtime directory

#### Scenario: Failed, interrupted and expired runs
- **WHEN** the wall exits before readiness, a start is killed after seeding, or a lease expires after handoff
- **THEN** doctor lists the run as failed, starting or expired, stop removes only what that run created, and frozen proof still verifies

#### Scenario: Concurrent runs and restart
- **WHEN** two runs serve at once and one is reseeded, or a run is restarted
- **THEN** the other run keeps its state and process, and the restarted run names its predecessor and whether the candidate is the same

#### Scenario: Restart after expiry
- **WHEN** an expired, handed-off run is handed off again and then restarted
- **THEN** the handoff reports `run-not-running`, the new run names the expired run and whether the candidate is the same, and the expired run's verified `SHA256SUMS` is unchanged
