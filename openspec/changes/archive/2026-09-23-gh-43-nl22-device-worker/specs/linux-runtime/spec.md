## MODIFIED Requirements

### Requirement: Coordinated services and one light writer

Linux hooks, CLI, map, and controller SHALL use the same Linux state and existing transactions. Concurrent worker launches SHALL retain one active light writer per registered device, and each writer SHALL address only its own device. The map, controller, and MCP SHALL have foreground commands and user service units; the worker SHALL remain on demand. Installation SHALL keep service activation and physical acceptance distinct from source verification. This maps to #54 A2, A5-A7 and [#43](https://github.com/jimmie-potts/codex-nanoleaf/issues/43) AC9.

#### Scenario: Concurrent clients

- **WHEN** hooks, browser, and authenticated controller clients request changes concurrently
- **THEN** existing state coordination serializes the changes and each device's worker lock admits only one light writer for that device while preserving request identity and mode behavior

#### Scenario: Service operation

- **WHEN** the operator starts the user services in WSL
- **THEN** the map, controller, and MCP run as separate Linux foreground processes with the configured state and ports
- **AND** availability follows WSL lifetime without requiring Windows startup automation
