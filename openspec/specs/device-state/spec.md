# device-state Specification

## Purpose
Describe more than one Nanoleaf device in one Linux installation without duplicating task ingestion or losing the existing Lines configuration. Scope is [issue #41](https://github.com/jimmie-potts/codex-nanoleaf/issues/41).

## Requirements

### Requirement: Shared task data keeps one owner
Task history, task identities, project identity, task-project overrides, status epochs, tool waits and Codex unread evidence SHALL remain single shared records. Device-scoped records SHALL reference those shared task and project identities rather than copying them. Covers #41 AC1.

#### Scenario: Two devices share one task
- **WHEN** one task holds a placement on two registered devices
- **THEN** the task, its status epoch and its project override exist once, and each device's placement references that same task identity

### Requirement: Device registry and stable identity
The private configuration SHALL record each device's id, kind (`lines` or `panels`), address and token reference. The original Lines device SHALL keep the controller identity established by #28 (`wall`) and SHALL be implied when a configuration predates the registry. A configured address change SHALL NOT change a device's identity or its saved state. Element identity SHALL be qualified by device so that equal physical panel IDs on two devices never collide. Covers AC2.

#### Scenario: Address change keeps identity
- **WHEN** the operator changes the configured address of the original Lines device
- **THEN** the device keeps id `wall`, and its reservations, placements and settings remain associated with it

#### Scenario: Equal panel IDs on two devices
- **WHEN** two registry entries both expose an element built from panel ID 5
- **THEN** each device keeps its own reservation, placement and pending edit for that element without overwriting the other

### Requirement: Device-scoped state
Slot assignments, comets, Line preferences, display cache, map settings, pending map edits, Locate, mode and the saved scene SHALL be keyed by device. Uniqueness SHALL be device plus slot and device plus element, so one task can hold one placement per device. Covers AC3.

#### Scenario: One placement per device
- **WHEN** a task is placed on slot 0 of the Lines device and slot 0 of a Panels device
- **THEN** both placements are stored, while a second task cannot take slot 0 on the same device

#### Scenario: Independent modes and scenes
- **WHEN** Quiet is selected for a second device
- **THEN** the original Lines device stays in its current mode and its saved scene file is untouched

### Requirement: Per-device layout shape
The layout file SHALL hold one entry per device. Each element SHALL carry its physical ID, its existing number and a zone list with two zones for a Line and one zone for a triangle. Task assignment and map presentation SHALL read that shape. A legacy Lines-only layout SHALL still load as the original device. Initialization SHALL reject a malformed layout and keep the last valid file. Covers AC4.

#### Scenario: Legacy layout loads unchanged
- **WHEN** an installation still has a Lines-only layout file
- **THEN** its Lines keep their numbers, zone pairs and positions under the original device, and no device request is needed

#### Scenario: Malformed layout is rejected
- **WHEN** a saved layout has an element with the wrong zone count, a duplicate zone or a non-numeric zone
- **THEN** initialization fails with an error, no request is sent, and the previous valid file remains on disk

### Requirement: Idempotent Linux migration
Existing Linux state SHALL migrate inside the existing initialization with guarded schema changes that default every existing row to the original Lines device. Repeated initialization SHALL change nothing. Tasks, project and half preferences, scene choice and brightness, an active comet, pending edits, mode metadata and protected-API credentials and request history SHALL survive with their values and epochs intact. Covers AC5.

#### Scenario: Pre-change database initializes twice
- **WHEN** a copy of a pre-change Linux database is initialized twice
- **THEN** every preserved value and epoch matches the original, the second initialization is a no-op, and the existing machine credential still authenticates

### Requirement: Default device for untargeted callers
Callers that name no device SHALL address the original Lines device. Existing Lines-only behavior, the Python suite and the browser checks SHALL pass unchanged apart from the new device parameter. Covers AC6.

#### Scenario: Untargeted call
- **WHEN** existing code reads settings, pending edits, mode or placements without naming a device
- **THEN** it receives the original Lines device's values
