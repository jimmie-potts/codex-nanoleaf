# device-worker Specification

## Purpose
Run the existing worker for each registered Nanoleaf device, so Lines and NL22 Light Panels mirror the same tasks with their own placement, mode, scene, effects and failures, while task ingestion stays single and each device's worker owns that device's protected-controller ledger. Scope is [issue #43](https://github.com/jimmie-potts/codex-nanoleaf/issues/43), which absorbed #42, and [issue #113](https://github.com/jimmie-potts/codex-nanoleaf/issues/113) for per-device controller ledgers.

## Requirements

### Requirement: One worker instance per device
The existing worker program SHALL run as one locked instance per registered device. Each instance SHALL send light updates only to its own device's address and credential. Waking the worker SHALL wake every registered device's instance. A second instance for the same device SHALL exit without sending. One ingestion path SHALL remain: only the original Lines instance (`wall`) polls the shared feed and processes integration-settings requests and requested animations. Each instance SHALL process its own device's protected-controller requests. Every instance SHALL reconcile shared Codex read evidence. Covers [#43](https://github.com/jimmie-potts/codex-nanoleaf/issues/43) AC9 and the issue's ownership scope, amended by [#113](https://github.com/jimmie-potts/codex-nanoleaf/issues/113).

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
Each device SHALL persist its own Work, Quiet and Free selection, applied revision and error. Each device SHALL restore its own latest saved scene and brightness across takeover, idle, Quiet, Free and recoverable failure. Quiet SHALL use the steady 10 percent policy, and Work SHALL keep its brightness policy. A change to one device SHALL NOT clear the other device's effects, pending edits, mode or restoration state. After a successful Free handoff, the device SHALL receive no further requests except the single write of an explicit native power, brightness, scene or animation command on the original Lines device; Free SHALL NOT poll or send task lighting. Display-cache clears and previews SHALL affect only their target device. `setup --reset` and shared-source switching SHALL state that they reset every device, and shared-source switching SHALL preserve bound placements on every device. Covers AC3 and [issue #92](https://github.com/jimmie-potts/codex-nanoleaf/issues/92).

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

### Requirement: Unregistered device instance stops
A worker instance for a device other than the original Lines device SHALL stop when that device is no longer registered. It SHALL NOT retry, record errors or send requests for an unregistered device. The original Lines instance SHALL be unaffected. Covers [#45](https://github.com/jimmie-potts/codex-nanoleaf/issues/45) AC4 removal.

#### Scenario: Device removed while its worker waits
- **WHEN** a Panels instance is waiting between passes and the Panels registration is removed
- **THEN** the instance exits at its next pass without sending, and the Lines instance keeps running

#### Scenario: Retry after removal
- **WHEN** a Panels instance's pass failed and the device is then unregistered
- **THEN** the instance stops instead of recording another error and retrying

### Requirement: Requested animation playback
The original Lines instance SHALL play a queued extension animation only while its mode is Free, as one journaled `PUT /effects` display write through its existing light transport, with no per-frame streaming and no brightness or power write. A pending mode command SHALL apply first; queued v1 controls and animations SHALL then run oldest first by admission. The worker SHALL encode status and animation effects with one shared frame encoder, and status payloads SHALL stay byte-identical. Every pattern SHALL use the saved Lines geometry, give both zones of a Line the same frames and stay within the extension's frame and byte bounds. Panels instances SHALL never play extension animations. Maps to [issue #92](https://github.com/jimmie-potts/codex-nanoleaf/issues/92) scope 2 and 3 and its encoder criterion.

#### Scenario: Animation after the Free handoff
- **WHEN** a Free mode command and an animation are both pending in one pass
- **THEN** the Free handoff write happens first, the animation's display write follows, and the animation receipt ends `sent`

#### Scenario: Pattern encoding on fixture layouts
- **WHEN** each pattern renders on the 15-Line fixture and a two-Line layout
- **THEN** every zone gets a positive-duration frame list within 20 frames, paired zones match, spatial patterns order their phases along the requested direction, and the request body is at most 8,192 bytes

#### Scenario: Status encoding unchanged
- **WHEN** a status display is encoded through the shared encoder
- **THEN** its payload equals the payload produced before the encoder was extracted

### Requirement: Address follows the registry
Each worker pass SHALL send to the address and credential currently registered for its device. A registered address change SHALL take effect on the running instance's next pass, or on its next retry after a failed pass, without a service restart. A pass SHALL keep its previous transport when the configuration cannot be read. Covers [#114](https://github.com/jimmie-potts/codex-nanoleaf/issues/114) AC3.

#### Scenario: Running worker follows a changed address
- **WHEN** a Panels worker instance is running in Work and the operator changes its registered address
- **THEN** its later light writes go to the new address and none go to the old one, without restarting the instance

### Requirement: Each device owns its controller ledger
Each worker instance SHALL recover, hold, journal and execute only its own device's protected-controller work: mode, power, brightness and `scene.activate` requests, overrides, the hold on a failed or uncertain machine request, and saved-scene discovery. An instance SHALL never execute, finish, hold or recover another device's controller requests. A device without a configured ledger SHALL receive no machine requests. Covers [#113](https://github.com/jimmie-potts/codex-nanoleaf/issues/113) scope 2 and AC1.

#### Scenario: A command runs only on its own device's worker
- **WHEN** a machine client sends brightness to the Panels and power to the Lines with both instances running
- **THEN** only the Panels transport receives the brightness write, only the Lines transport receives the power write, and each receipt is finished by its own device's instance

#### Scenario: Hold on one device leaves the other running
- **WHEN** an uncertain machine write holds the Panels
- **THEN** the Panels instance stops its automatic retries, the Lines instance keeps rendering tasks and accepts a new machine command, and the Lines ledger has no hold

#### Scenario: Per-device revisions and scenes
- **WHEN** each worker observes its own device's saved scenes, and a mode command is admitted for one device
- **THEN** each ledger advertises only its own device's scene IDs, and only the commanded device's configuration revision and generation advance

#### Scenario: Machine requests never reach an unconfigured device
- **WHEN** Panels are registered but the controller has no Panels ledger, and a client sets Quiet, brightness and power on the Lines
- **THEN** only the Lines transport receives those writes, the Panels mode and transport are unaffected, and the protected contract fixtures are unchanged

### Requirement: Circular directions and faster requested animation
Spatial requested patterns SHALL support `clockwise` and `counterclockwise` around the centroid of the saved Line positions using positive Y upwards, with a full circular phase starting at positive X. A Line at the centroid SHALL use phase zero. The `faster` speed SHALL use a one-decisecond base keyframe step and shorten each pattern's cycle relative to `fast`. All existing direction and speed combinations SHALL preserve encoded payload bytes. Frame and request byte limits, Free-only playback, receipts and single-writer ownership SHALL remain unchanged. Maps to [issue #151](https://github.com/jimmie-potts/codex-nanoleaf/issues/151) encoder acceptance and retained protections.

#### Scenario: Rotating crests on both fixture layouts
- **WHEN** wave or gradient renders a clockwise or counterclockwise rotation on the 15-Line or two-Line fixture
- **THEN** the crest follows the corresponding centroid angle within keyframe quantization, both zones agree, and the existing frame and byte limits hold

#### Scenario: Faster cycle with legacy compatibility
- **WHEN** each pattern uses `faster`
- **THEN** its cycle is shorter than `fast` without zero-duration frames
- **AND** rendering any old direction and speed combination produces the original bytes
