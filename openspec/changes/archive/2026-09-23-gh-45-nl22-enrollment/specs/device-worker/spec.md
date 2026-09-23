## MODIFIED Requirements

### Requirement: Per-device failure isolation
A failed pass SHALL be caught for its device, recorded under that device's error and retried after the existing bounded two-second delay, unless the device is no longer registered (see "Unregistered device instance stops"). A failing device SHALL NOT abort the other device's due updates or overwrite its last successful outcome, error or the controller's receipts. Covers AC5.

#### Scenario: Panels outage
- **WHEN** the Panels transport fails while both devices have tasks
- **THEN** Lines still renders its due update with no error, Panels reports its own error and retries, and the controller's last outcome is unchanged

## ADDED Requirements

### Requirement: Unregistered device instance stops
A worker instance for a device other than the original Lines device SHALL stop when that device is no longer registered. It SHALL NOT retry, record errors or send requests for an unregistered device. The original Lines instance SHALL be unaffected. Covers [#45](https://github.com/jimmie-potts/codex-nanoleaf/issues/45) AC4 removal.

#### Scenario: Device removed while its worker waits
- **WHEN** a Panels instance is waiting between passes and the Panels registration is removed
- **THEN** the instance exits at its next pass without sending, and the Lines instance keeps running

#### Scenario: Retry after removal
- **WHEN** a Panels instance's pass failed and the device is then unregistered
- **THEN** the instance stops instead of recording another error and retrying
