## Purpose

Run the Nanoleaf application in a private Linux installation while retaining its existing task interpretation, controller API, browser map, and single light writer.

## ADDED Requirements

### Requirement: Private fresh Linux installation

The installation SHALL accept a configured private device address and a privately supplied credential, create its own Linux state with owner-only access, and keep runtime SQLite off Windows-mounted filesystems. It SHALL provision the required Python and Node runtime files without importing previous project data or modifying unrelated application data. This maps to #54 A1 and A7.

#### Scenario: Fresh setup with private configuration

- **WHEN** an operator supplies valid device configuration and an empty Linux destination
- **THEN** setup validates the device and creates the Linux runtime, private configuration, and separate machine credentials without launching a Windows executable or sending a light write

#### Scenario: Unsuitable destination or invalid configuration

- **WHEN** the state directory resolves to a Windows-mounted path, already contains an installation, or device validation fails
- **THEN** setup fails without changing the user's hook configuration or disclosing credentials

### Requirement: Linux hooks and metadata remain local

Linux hooks SHALL use the installation's Python and explicit Linux state directory. Hook registration SHALL replace only this integration's marked handlers and preserve unrelated settings and handlers. Configured Desktop JSON inputs SHALL remain read-only and retain existing conservative missing/malformed-data behavior. This maps to #54 A2 and A3.

#### Scenario: WSL lifecycle event

- **WHEN** a lifecycle event reaches a registered Linux hook
- **THEN** it updates the designated Linux state and may wake the existing worker without calling Windows or waiting for the light operation

#### Scenario: Missing metadata

- **WHEN** configured project, title, or unread JSON cannot be read reliably
- **THEN** the existing reader retains its conservative behavior and does not modify Codex data

### Requirement: Stable local service commands

The installation SHALL provide configurable distinct loopback ports with defaults 8765 for the map, 41231 for the controller, and 41230 for MCP. A configured occupied port SHALL fail with a useful error. Linux map access SHALL print the usable local URL without launching a browser or Windows executable. This maps to #54 A4-A6.

#### Scenario: Browser URL and port collision

- **WHEN** the operator requests the Linux map URL
- **THEN** the command verifies or starts this installation's map at its configured port and prints its URL without launching a browser
- **AND** an occupied port belonging to another service produces a failure instead of an alternative port

### Requirement: Coordinated services and one light writer

Linux hooks, CLI, map, and controller SHALL use the same Linux state and existing transactions. Concurrent worker launches SHALL retain one active light writer. The map, controller, and MCP SHALL have foreground commands and user service units; the worker SHALL remain on demand. Installation SHALL keep service activation and physical acceptance distinct from source verification. This maps to #54 A2, A5-A7.

#### Scenario: Concurrent clients

- **WHEN** hooks, browser, and authenticated controller clients request changes concurrently
- **THEN** existing state coordination serializes the changes and the worker lock admits only one light writer while preserving request identity and mode behavior

#### Scenario: Service operation

- **WHEN** the operator starts the user services in WSL
- **THEN** the map, controller, and MCP run as separate Linux foreground processes with the configured state and ports
- **AND** availability follows WSL lifetime without requiring Windows startup automation
