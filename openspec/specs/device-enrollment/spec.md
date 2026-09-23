# device-enrollment Specification

## Purpose
Add NL22 Light Panels to an existing Linux Lines installation, and remove them again, without fresh setup and without disturbing Lines, shared tasks, hooks or machine credentials. Scope is [issue #45](https://github.com/jimmie-potts/codex-nanoleaf/issues/45).

## Requirements

### Requirement: Verified enrollment
An explicit enrollment command SHALL accept a private NL22 address and a credential supplied through a hidden prompt, a private token file or the device's pairing window. It SHALL verify that the device reports model NL22 and a valid triangle layout before it writes anything. It SHALL then register the device under a stable id, defaulting to `panels`, with kind `panels`. It SHALL NOT run fresh setup, clear tasks, change hooks, or alter the `wall` identity, address, credential or layout entry. Covers #45 AC1.

#### Scenario: Enroll Panels beside Lines
- **WHEN** the operator enrolls a fake NL22 device into Linux state that holds Lines, tasks, reservations, a Lines mode and registered hooks
- **THEN** the registry lists the Panels id with its address and a private credential reference, the layout holds its reported triangles, and the Lines entry, tasks, reservations, Lines mode and hooks file are unchanged

#### Scenario: Pairing supplies the credential
- **WHEN** the operator enrolls with the pairing option while the fake device's pairing window is open
- **THEN** the command obtains the credential from the device, stores it privately and never prints it

#### Scenario: Wrong model or unusable layout
- **WHEN** the device reports a model other than NL22, or a layout with an unsupported shape, overlap or disconnection
- **THEN** enrollment fails with a reason, and the configuration, layout and state are unchanged

### Requirement: Private enrollment state
Device addresses, credentials, reported layout and device state SHALL be stored only in the private Linux state directory, in owner-only files. Credentials SHALL NOT appear in command output, error messages, browser responses or repository fixtures. Enrollment and removal SHALL refuse a Windows-mounted state directory and SHALL NOT run on Windows. Covers #45 AC2.

#### Scenario: Credential stays private
- **WHEN** enrollment succeeds or fails after reading a credential
- **THEN** the configuration and layout files are owner-only, the credential is absent from the command's output and from the wall map's state response, and the synthetic fixtures contain no real credential

#### Scenario: Windows-mounted state
- **WHEN** the state directory is under a Windows-mounted drive
- **THEN** enrollment and removal fail without reading or writing that state

### Requirement: Free start without replay
A newly enrolled device SHALL start in Free with no pending mode change. Its worker SHALL send no request to it until the operator explicitly selects Work or Quiet for it. Enrollment SHALL save the reported geometry, so the worker needs no discovery request. Activation SHALL NOT replay completion comets or outward waves from before activation. Covers #45 AC3.

#### Scenario: Enrolled device stays dark
- **WHEN** tasks are active and the newly enrolled device's worker runs
- **THEN** the fake NL22 transport receives no request, and `status --device panels` reports Free with nothing pending

#### Scenario: Activation shows only current status
- **WHEN** tasks completed while Panels was in Free and the operator then selects Work for Panels
- **THEN** no comet is queued for Panels, its wave cutoff is the activation time, and Lines' comets and mode are unchanged

### Requirement: Conflicts and repeats keep existing state
Enrollment SHALL refuse the reserved `wall` id, an invalid id, an address used by another registered device, an existing id registered at a different address or as a different kind, and a repeat for an id whose credential key another device shares. It SHALL run these checks before it asks the operator or the device for a credential. It SHALL NOT silently redirect an existing identity. Repeating enrollment for the same id and address SHALL replace only its credential and SHALL keep its layout, mode, reservations and scene. A failed enrollment SHALL leave every device and all shared tasks intact. Enrollment SHALL NOT issue, revoke or change machine credentials. The protected controller API SHALL stay Lines-only. Saved geometry and preferences SHALL stay usable while the device is unreachable. Covers #45 AC4.

#### Scenario: Address and identity conflicts
- **WHEN** the operator enrolls with id `wall`, with the Lines address, or with the registered Panels id at a new address
- **THEN** the command fails, and the configuration, layout and state are unchanged

#### Scenario: Conflict found before a credential is requested
- **WHEN** the operator enrolls with the pairing option or the hidden prompt at an address another device uses
- **THEN** the command fails without pairing or prompting

#### Scenario: Shared credential on repeat
- **WHEN** a hand-edited Panels entry refers to the Lines credential and the operator repeats its enrollment
- **THEN** the command fails, and the Lines credential is unchanged

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

### Requirement: Explicit removal
A removal command SHALL remove a registered non-Lines device's registration, credential, layout entry, device-scoped state and saved scene. It SHALL require the device to be in Free with that mode applied, unless the operator forces removal of an unreachable device. It SHALL stop that device's worker, and it SHALL leave Lines, shared tasks and other devices unchanged. If the worker does not stop in time, or a failure follows the first state write, the command SHALL say so, and rerunning it SHALL finish the cleanup. Covers #45 AC4 and AC6.

#### Scenario: Remove Panels after Free
- **WHEN** Panels is in Free with the handoff applied and the operator removes it
- **THEN** the registry, credential, layout entry, Panels rows and scene file are gone, and Lines' entry, mode, reservations and tasks are unchanged

#### Scenario: Removal before handoff
- **WHEN** the operator removes Panels while it is in Work or its Free change is still pending
- **THEN** the command refuses without the force option and explains how to hand the device back first, and with the force option it removes the device

#### Scenario: Failure after the registration is removed
- **WHEN** removal fails after it has removed the registration, for example on a malformed layout file
- **THEN** the command does not claim that nothing changed, and it asks the operator to run it again

#### Scenario: Removing Lines
- **WHEN** the operator tries to remove `wall` or an unknown id
- **THEN** the command fails and nothing changes

### Requirement: Operator guidance without restarts
Enrollment SHALL tell the operator how to activate the device and that no user service needs a restart, because hooks and the worker read the registry when they start and the map, controller and MCP stay Lines-only. Listener configuration, trusted hooks, selected modes, reservations and pulse and comet epochs SHALL be preserved. Covers #45 AC5.

#### Scenario: Enrollment output
- **WHEN** enrollment succeeds
- **THEN** its output names the activation command for the new id and states that no service restart is needed, and the listener ports in the configuration are unchanged
