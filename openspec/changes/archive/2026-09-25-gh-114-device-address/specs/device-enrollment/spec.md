## ADDED Requirements

### Requirement: Verified address change
An explicit address command SHALL change the registered address of one registered Panels device and nothing else. The device SHALL keep its id, credential reference, reservations, mode, layout entry and saved scene, and SHALL stay registered once. Before any write the command SHALL require a private IPv4 address that no other registered device uses, and SHALL verify with the stored credential that the device at the new address reports model NL22 and a triangle layout equal to the saved one, with the same triangles, positions and neighbors. A failed check, an unreachable address, an unknown id or the Lines id `wall` SHALL be refused with nothing changed. The command SHALL send no light write, and SHALL keep credentials out of its output and errors. Covers [#114](https://github.com/jimmie-potts/codex-nanoleaf/issues/114) AC1, AC2 and AC4.

#### Scenario: Change the Panels address
- **WHEN** the operator changes the address of an enrolled Panels device that holds a mode, a reservation, a layout and a saved scene, and the fake NL22 device answers at the new address with the same triangles
- **THEN** only the registry entry's address changes, the device is listed once, its mode, reservation, layout and scene are unchanged, and the only device request is one read of the new address

#### Scenario: Address in use or not private
- **WHEN** the new address is the Lines address, another registered device's address, or a public or non-IPv4 address
- **THEN** the command fails before contacting any device, and the configuration, layout and state are unchanged

#### Scenario: Different device at the new address
- **WHEN** the device at the new address reports another model, or triangles that differ from the saved layout
- **THEN** the command fails with a reason, and the configuration, layout and state are unchanged

#### Scenario: Unreachable new address
- **WHEN** the new address does not answer
- **THEN** the command fails, and nothing is written

#### Scenario: Lines or unknown id
- **WHEN** the operator names `wall` or an unregistered id
- **THEN** the command fails without contacting a device, and nothing changes

#### Scenario: Credential stays private
- **WHEN** the address change succeeds or fails
- **THEN** the stored credential is absent from the command's output and errors
