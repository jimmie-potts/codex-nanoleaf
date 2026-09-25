## MODIFIED Requirements

### Requirement: Explicit authenticated local hosting
The integration SHALL expose an opt-in loopback MCP host using the immutable shared module, fixed server-configured targets and current machine credentials. It SHALL run beside the Linux installation without a standalone hub or new remote ingress. This maps to issue #33 criteria 1, 2, 5, 6 and 7 and to [issue #131](https://github.com/jimmie-potts/codex-nanoleaf/issues/131) AC3.

#### Scenario: Native initialization and scoped discovery
- **WHEN** a native client initializes using a current machine credential and no Origin
- **THEN** the shared handler authenticates it and discovery contains only the configured target's tools allowed by its current scopes
- **AND** the tool surface exposes no power, brightness, scene, zone or raw command, whatever the controller advertises

#### Scenario: Invalid transport or revoked principal
- **WHEN** the path, Host, supplied Origin or credential is invalid, or a principal is removed before new dispatch
- **THEN** the call is rejected before controller dispatch
- **AND** ordinary hooks, wall editor and worker remain unaffected

### Requirement: Immutable source qualification and acceptance boundary
The source SHALL pin and verify the released shared package, provide the Linux client template and qualify both supported MCP versions with fake-controller protocol tests. Installation and physical acceptance SHALL remain separately authorized, as recorded for the Linux fresh install in #55. This maps to issue #33 criteria 7 and 8.

#### Scenario: Isolated consumer validation
- **WHEN** the source is installed and tested without sibling repositories, personal credentials or devices
- **THEN** the vendored artifact, installed manifest and shared contract validate and real protocol fixtures cover the loopback route and qualified versions

#### Scenario: Source handoff
- **WHEN** source checks pass
- **THEN** the handoff reports source revision and test evidence separately from unperformed installed Codex, deployment and physical-light observations

## ADDED Requirements

### Requirement: Bounded loopback transport
The MCP host SHALL call only its configured numeric loopback controller over direct HTTP. The transport identifier SHALL be `loopback-http`; a configuration naming the earlier `windows-http` identifier SHALL be accepted as the same transport so an installed configuration keeps validating. No other transport, helper process or configuration key for one SHALL be accepted. No MCP route SHALL open the bridge database, launch a worker directly, accept arbitrary destinations or expose credentials. This maps to issue #33 criteria 5, 6 and 8 and to issue #131 AC3.

#### Scenario: Linux direct HTTP exchange
- **WHEN** the MCP host uses either accepted transport identifier for its Linux controller
- **THEN** it sends the same authenticated bounded controller requests over numeric loopback

#### Scenario: Broken or hostile transport
- **WHEN** configuration is missing or input, response, timing or concurrency exceeds its bound
- **THEN** the call settles with a bounded failure and no database access or automatic retry
- **AND** possible effects after dispatch remain uncertain

#### Scenario: Helper configuration is rejected
- **WHEN** a configuration names another transport or supplies helper keys such as a Windows runtime path
- **THEN** the host refuses the configuration before listening

## REMOVED Requirements

### Requirement: Bounded Windows and WSL transport
**Reason**: The Windows runtime and its WSL-to-Windows helper are retired under issue #131; the Linux installation uses direct loopback HTTP only, specified by the added "Bounded loopback transport" requirement.
**Migration**: Installed Linux configurations keep the `windows-http` identifier as an accepted alias of `loopback-http`; no operator action is required. Windows and WSL-helper configurations have no supported target.
