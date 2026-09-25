## MODIFIED Requirements

### Requirement: Operator guidance without restarts
Enrollment SHALL tell the operator how to activate the device and that no user service needs a restart, because hooks, the worker and the map read the registry when they need it. It SHALL also state that the controller and MCP reach the device only after `controller-configure` adds it ([#113](https://github.com/jimmie-potts/codex-nanoleaf/issues/113)). Listener configuration, trusted hooks, selected modes, reservations and pulse and comet epochs SHALL be preserved. Covers #45 AC5.

#### Scenario: Enrollment output
- **WHEN** enrollment succeeds
- **THEN** its output names the activation command for the new id and states that no service restart is needed and how to add the device to the controller, and the listener ports in the configuration are unchanged

### Requirement: Conflicts and repeats keep existing state
Enrollment SHALL refuse the reserved `wall` id, an invalid id, an address used by another registered device, an existing id registered at a different address or as a different kind, and an id whose credential key another device already uses. It SHALL run these checks before it asks the operator or the device for a credential. Enrollment and removal SHALL refuse a malformed saved layout before any write, because a rerun cannot repair it. It SHALL NOT silently redirect an existing identity. Repeating enrollment for the same id and address SHALL replace only its credential and SHALL keep its layout, mode, reservations and scene. A failed enrollment SHALL leave every device and all shared tasks intact. Enrollment SHALL NOT issue, revoke or change machine credentials. The protected controller API SHALL reach an enrolled device only after `controller-configure` adds its ledger ([#113](https://github.com/jimmie-potts/codex-nanoleaf/issues/113)). Saved geometry and preferences SHALL stay usable while the device is unreachable. Covers #45 AC4.

#### Scenario: Address and identity conflicts
- **WHEN** the operator enrolls with id `wall`, with the Lines address, or with the registered Panels id at a new address
- **THEN** the command fails, and the configuration, layout and state are unchanged

#### Scenario: Conflict found before a credential is requested
- **WHEN** the operator enrolls with the pairing option or the hidden prompt at an address another device uses
- **THEN** the command fails without pairing or prompting

#### Scenario: Shared credential key
- **WHEN** a hand-edited entry refers to the Lines credential and the operator repeats its enrollment, or another entry already uses the new id's credential key
- **THEN** the command fails, and every stored credential is unchanged

#### Scenario: Malformed saved layout
- **WHEN** the saved layout file is malformed
- **THEN** enrollment and removal fail before any write and name the file to repair

#### Scenario: Repeat enrollment
- **WHEN** the operator enrolls the same id at the same address again with a new credential, after choosing Quiet and a reservation for it
- **THEN** only the stored credential changes, and its Quiet mode, reservation and layout are kept

#### Scenario: Device unreachable during enrollment
- **WHEN** the device request fails
- **THEN** enrollment fails, and nothing is written

#### Scenario: Machine credentials unchanged
- **WHEN** enrollment succeeds in state that has controller and MCP credentials
- **THEN** the controller credential records and the MCP credential files are identical to before

#### Scenario: Cached geometry offline
- **WHEN** an enrolled device's address stops answering
- **THEN** its configuration and layout still load without a device request
