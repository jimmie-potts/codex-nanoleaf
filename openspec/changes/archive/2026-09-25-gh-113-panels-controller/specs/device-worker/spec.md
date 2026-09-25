## MODIFIED Requirements

### Requirement: One worker instance per device
The existing worker program SHALL run as one locked instance per registered device. Each instance SHALL send light updates only to its own device's address and credential. Waking the worker SHALL wake every registered device's instance. A second instance for the same device SHALL exit without sending. One ingestion path SHALL remain: only the original Lines instance (`wall`) polls the shared feed and processes integration-settings requests and requested animations. Each instance SHALL process its own device's protected-controller requests. Every instance SHALL reconcile shared Codex read evidence. Covers [#43](https://github.com/jimmie-potts/codex-nanoleaf/issues/43) AC9 and the issue's ownership scope, amended by [#113](https://github.com/jimmie-potts/codex-nanoleaf/issues/113).

#### Scenario: Independent writers
- **WHEN** a hook wakes the worker with Lines and Panels registered
- **THEN** one instance per device runs, each sends only to its own fake transport, and a concurrent launch for either device exits without sending

#### Scenario: Only Lines polls the shared feed
- **WHEN** shared input is selected and both instances run
- **THEN** only the `wall` instance fetches the shared snapshot, and the Panels instance renders the projected tasks

## REMOVED Requirements

### Requirement: Protected APIs stay on Lines
**Reason**: [#113](https://github.com/jimmie-potts/codex-nanoleaf/issues/113) makes the Panels a second controller device, and [ADR 0015](../../../docs/decisions/0015-per-device-controller-ledgers.md) replaces ADR 0010's single-owner rule.
**Migration**: "Each device owns its controller ledger" replaces this requirement. A registry without a Panels ledger behaves as before: machine requests reach only the Lines, and the Lines' contract fixtures are unchanged.

## ADDED Requirements

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
