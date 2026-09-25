## ADDED Requirements

### Requirement: Supported modes preserve Linux ownership

The controller SHALL advertise Work, Quiet and Free as supported modes, power as supported, brightness as supported with the typed 0 to 100 bound, and scenes as supported with the discovered saved-scene identities bounded to 256 IDs; media, zones and preview SHALL remain unsupported. Accepted mode requests SHALL use the installation's existing Linux state coordination and single light worker. Existing mode brightness, scene restoration, pulse timing, unread behavior, project reservations SHALL remain intact. Installed commands SHALL open only the installation's own Linux state; no command SHALL forward to another operating system. This requirement maps to issue #28's worker-ownership and unavailable-preview criteria, to [issue #64](https://github.com/jimmie-potts/codex-nanoleaf/issues/64) AC1 and to [issue #131](https://github.com/jimmie-potts/codex-nanoleaf/issues/131) AC1 and AC2; the retained baseline is the [bridge guide](../../../bridge/README.md).

#### Scenario: A client requests Quiet

- **WHEN** an authorized fresh command requests Quiet
- **THEN** the existing worker applies the current Quiet policy and the API does not independently send a light request

#### Scenario: A client requests unsupported brightness or preview

- **WHEN** a client inspects capabilities, requests a brightness outside 0 to 100, or requests a media, zone or preview operation
- **THEN** power, brightness and scenes are declared supported with their typed constraints, the out-of-range brightness fails validation, media, zones and preview are explicitly unavailable, and the unsupported operation is rejected through the shared contract without a new effect

#### Scenario: Linux-owned controller command

- **WHEN** a controller command targets the Linux installation
- **THEN** it uses only that installation's Linux state and worker, and the installed command surface contains no forwarding entry point

## REMOVED Requirements

### Requirement: Supported modes preserve existing ownership
**Reason**: Its legacy Windows forwarding boundary and WSL dispatch scenario are retired under issue #131. The added "Supported modes preserve Linux ownership" requirement carries the unchanged mode, control and worker-ownership behavior forward.
**Migration**: None for the Linux installation; installed commands already open only Linux state.
