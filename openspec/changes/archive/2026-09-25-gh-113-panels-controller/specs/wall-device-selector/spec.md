## MODIFIED Requirements

### Requirement: Device-scoped map API

State reads and the mode, settings, assignment, Locate and eviction actions SHALL accept a registered device, state through a query parameter and actions through a `device` field. Requests naming no device SHALL address the original Lines device, so existing browser and CLI callers behave as before. Requests naming an unregistered device SHALL be rejected without addressing Lines and without changing state; a rejected state read SHALL still name the registered devices. Project colours and task project assignment SHALL stay shared across devices. The protected controller API, the read-only integration settings extension for other devices and the optional MCP Panels target SHALL reach another device only after `controller-configure` adds its ledger ([#113](https://github.com/jimmie-potts/codex-nanoleaf/issues/113)). Covers AC2.

#### Scenario: Untargeted request
- **WHEN** a state read or an action names no device
- **THEN** it addresses the Lines device, whatever the registry order

#### Scenario: Targeted request
- **WHEN** a state read or an action names the Panels
- **THEN** it reads or changes only the Panels' state, mode, layout settings, reservations or Locate

#### Scenario: Unknown device
- **WHEN** a state read or an action names a device that is not registered
- **THEN** it is rejected, nothing changes on any device, and the rejection lists the registered devices

#### Scenario: Shared project colour
- **WHEN** a project colour is changed while the Panels are selected
- **THEN** the Lines show the same colour
