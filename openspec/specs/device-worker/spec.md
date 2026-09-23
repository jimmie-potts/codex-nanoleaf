# device-worker Specification

## Purpose
Run the existing worker for each registered Nanoleaf device, so Lines and NL22 Light Panels mirror the same tasks with their own placement, mode, scene, effects and failures, while task ingestion and the protected APIs stay single. Scope is [issue #43](https://github.com/jimmie-potts/codex-nanoleaf/issues/43), which absorbed #42.

## Requirements

### Requirement: One worker instance per device
The existing worker program SHALL run as one locked instance per registered device. Each instance SHALL send light updates only to its own device's address and credential. Waking the worker SHALL wake every registered device's instance. A second instance for the same device SHALL exit without sending. One ingestion path SHALL remain: only the original Lines instance (`wall`) polls the shared feed and processes protected-controller and integration-settings requests. Every instance SHALL reconcile shared Codex read evidence. Covers [#43](https://github.com/jimmie-potts/codex-nanoleaf/issues/43) AC9 and the issue's ownership scope.

#### Scenario: Independent writers
- **WHEN** a hook wakes the worker with Lines and Panels registered
- **THEN** one instance per device runs, each sends only to its own fake transport, and a concurrent launch for either device exits without sending

#### Scenario: Only Lines polls the shared feed
- **WHEN** shared input is selected and both instances run
- **THEN** only the `wall` instance fetches the shared snapshot, and the Panels instance renders the projected tasks

### Requirement: Mirrored per-device allocation
The same working task SHALL occupy at most one element on each device. Each device SHALL independently keep valid assignments, project reservations, Shared overflow, capacity and its waiting list. A full or failing device SHALL NOT move tasks to, or take tasks from, the other device. Covers AC1.

#### Scenario: One task on both devices
- **WHEN** one task starts working with both devices in Work
- **THEN** it holds one Line on the Lines device and one triangle on the Panels device, each showing the same status epoch

#### Scenario: Full device waits independently
- **WHEN** more tasks work than the Panels device has triangles
- **THEN** the extra tasks wait on Panels only, and the Lines device places them on its free Lines

### Requirement: Shared evidence and device-scoped queues
Completion and read evidence SHALL remain shared task records. Completion comets, active comet source reservations and pending display edits SHALL be device-scoped. A completion SHALL queue one comet on each registered device that is in Work. Reading a completed task through existing Codex evidence SHALL clear its indications on every device. The map and API SHALL never mark a task read. Covers AC2.

#### Scenario: Completion on two devices
- **WHEN** a task completes with Lines in Work and Panels in Quiet
- **THEN** one comet is queued for Lines, none for Panels, and both devices show the unread indication

#### Scenario: Reading clears both devices
- **WHEN** Codex's unread evidence no longer lists a completed task
- **THEN** its indications clear on both devices, and a queued comet on either device is dropped

### Requirement: Per-device modes and scene restoration
Each device SHALL persist its own Work, Quiet and Free selection, applied revision and error. Each device SHALL restore its own latest saved scene and brightness across takeover, idle, Quiet, Free and recoverable failure. Quiet SHALL use the steady 10 percent policy, and Work SHALL keep its brightness policy. A change to one device SHALL NOT clear the other device's effects, pending edits, mode or restoration state. After a successful Free handoff, the device SHALL receive no further requests. Display-cache clears and previews SHALL affect only their target device. `setup --reset` and shared-source switching SHALL state that they reset every device, and shared-source switching SHALL preserve bound placements on every device. Covers AC3.

#### Scenario: Mixed modes
- **WHEN** Lines is in Work and Panels is switched to Free
- **THEN** Panels restores its own saved scene once and receives no later requests, while Lines keeps rendering tasks and its comet and pending edits

#### Scenario: Targeted cache clear
- **WHEN** the operator refreshes the Panels device
- **THEN** only the Panels display cache is cleared, and the Lines worker sends nothing because of it

### Requirement: Effect continuity across device changes
Two-second status epochs, the one outward pulse, red and yellow priority and one completion comet per eligible completion per device SHALL be kept. Entering Work, registering a device, recovering a connection, switching layouts and editing project colors SHALL NOT reset epochs or replay obsolete effects. A new task-project override SHALL keep each device's active comet source until that comet's existing completion boundary. Covers AC4.

#### Scenario: Registering Panels later
- **WHEN** Panels is registered after tasks have completed and pulsed on Lines
- **THEN** the Panels instance shows current statuses with their existing epochs, and no wave or comet is replayed

#### Scenario: Override during a Panels comet
- **WHEN** a task's project is overridden while its comet is playing on Panels
- **THEN** the Panels comet source stays assigned until the comet ends, and only then is the task re-placed

### Requirement: Per-device failure isolation
A failed pass SHALL be caught for its device, recorded under that device's error and retried after the existing bounded two-second delay, unless the device is no longer registered (see "Unregistered device instance stops"). A failing device SHALL NOT abort the other device's due updates or overwrite its last successful outcome, error or the controller's receipts. Covers AC5.

#### Scenario: Panels outage
- **WHEN** the Panels transport fails while both devices have tasks
- **THEN** Lines still renders its due update with no error, Panels reports its own error and retries, and the controller's last outcome is unchanged

### Requirement: Explicit CLI device target
CLI `mode`, `status`, `worker` and device-specific `setup` operations SHALL accept an explicit `--device` target. Without a target they SHALL address the original Lines device, whatever the registry order. An unknown target SHALL be rejected without a state change. Covers AC6.

#### Scenario: Targeted mode
- **WHEN** the operator runs `mode quiet --device panels`
- **THEN** only the Panels mode changes, and `status` without a target still reports the Lines mode

#### Scenario: Unknown target
- **WHEN** the operator runs `mode free --device missing`
- **THEN** the command fails, and neither device's mode changes

### Requirement: Protected APIs stay on Lines
The protected controller, integration settings API and local MCP SHALL keep addressing only the original Lines identity. Their wire contract, capability declaration, snapshots, credentials and replay SHALL be unchanged. Power, brightness and saved-scene overrides, and the hold on failed or uncertain machine requests, SHALL apply to Lines only and SHALL never write to Panels. Registering Panels SHALL NOT change what any existing credential can do. Covers AC7.

#### Scenario: Machine requests never reach Panels
- **WHEN** a machine client sets Quiet, brightness and power while Panels is registered and in Work
- **THEN** only the Lines transport receives those writes, the Panels mode and transport are unaffected, and the protected contract fixtures are unchanged

#### Scenario: Hold is Lines-only
- **WHEN** an uncertain machine request holds the Lines instance
- **THEN** the Panels instance keeps rendering its tasks

### Requirement: Unregistered device instance stops
A worker instance for a device other than the original Lines device SHALL stop when that device is no longer registered. It SHALL NOT retry, record errors or send requests for an unregistered device. The original Lines instance SHALL be unaffected. Covers [#45](https://github.com/jimmie-potts/codex-nanoleaf/issues/45) AC4 removal.

#### Scenario: Device removed while its worker waits
- **WHEN** a Panels instance is waiting between passes and the Panels registration is removed
- **THEN** the instance exits at its next pass without sending, and the Lines instance keeps running

#### Scenario: Retry after removal
- **WHEN** a Panels instance's pass failed and the device is then unregistered
- **THEN** the instance stops instead of recording another error and retrying
