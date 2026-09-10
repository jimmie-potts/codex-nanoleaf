## MODIFIED Requirements

### Requirement: Supported modes preserve existing ownership

The controller SHALL advertise Work, Quiet and Free as supported modes and power, brightness, media, zones, scenes and preview as unsupported. Accepted mode requests SHALL use the installation's existing state coordination and single light worker on its owning operating system. Existing mode brightness, scene restoration, pulse timing, unread behavior, project reservations SHALL remain intact; legacy Windows installations SHALL retain their WSL forwarding boundary. This requirement maps to issue #28's worker-ownership and unavailable-preview criteria; the retained baseline is the [bridge guide](../../../bridge/README.md).

#### Scenario: A client requests Quiet

- **WHEN** an authorized fresh command requests Quiet
- **THEN** the existing worker applies the current Quiet policy and the API does not independently send a light request

#### Scenario: A client requests unsupported brightness or preview

- **WHEN** a client inspects capabilities or requests an unsupported brightness operation
- **THEN** preview is explicitly unavailable and unsupported control is rejected through the shared contract without a new effect

#### Scenario: Installed WSL command dispatch

- **WHEN** a WSL controller command targets the legacy Windows installation
- **THEN** it forwards to Windows before opening controller state, or fails without state changes when Windows is unavailable

#### Scenario: Linux-owned controller command

- **WHEN** a controller command targets the fresh Linux installation
- **THEN** it uses only that installation's Linux state and worker without Windows forwarding
