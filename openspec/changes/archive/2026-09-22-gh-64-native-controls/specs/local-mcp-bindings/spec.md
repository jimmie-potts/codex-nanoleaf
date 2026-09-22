## MODIFIED Requirements

### Requirement: Explicit authenticated local hosting
The integration SHALL expose an opt-in loopback MCP host using the immutable shared module, fixed server-configured targets and current machine credentials. It SHALL support Windows and WSL without a standalone hub or new remote ingress. This maps to issue #33 criteria 1, 2, 5, 6 and 7.

#### Scenario: Native initialization and scoped discovery
- **WHEN** a native client initializes using a current machine credential and no Origin
- **THEN** the shared handler authenticates it and discovery contains only the configured target's tools allowed by its current scopes
- **AND** the tool surface exposes no power, brightness, scene, zone or raw command, whatever the controller advertises

#### Scenario: Invalid transport or revoked principal
- **WHEN** the path, Host, supplied Origin or credential is invalid, or a principal is removed before new dispatch
- **THEN** the call is rejected before controller dispatch
- **AND** ordinary hooks, tray, wall editor and worker remain unaffected
