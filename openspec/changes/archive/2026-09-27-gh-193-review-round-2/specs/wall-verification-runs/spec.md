## MODIFIED Requirements

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
