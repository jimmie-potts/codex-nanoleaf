## ADDED Requirements

### Requirement: Unregistered device instance stops
A worker instance for a device other than the original Lines device SHALL stop when that device is no longer registered. It SHALL NOT retry, record errors or send requests for an unregistered device. The original Lines instance SHALL be unaffected. Covers [#45](https://github.com/jimmie-potts/codex-nanoleaf/issues/45) AC4 removal.

#### Scenario: Device removed while its worker waits
- **WHEN** a Panels instance is waiting between passes and the Panels registration is removed
- **THEN** the instance exits at its next pass without sending, and the Lines instance keeps running

#### Scenario: Retry after removal
- **WHEN** a Panels instance's pass failed and the device is then unregistered
- **THEN** the instance stops instead of recording another error and retrying
