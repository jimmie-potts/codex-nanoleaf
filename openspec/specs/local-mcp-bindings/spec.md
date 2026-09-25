# Local MCP bindings Specification

## Purpose

Provide authenticated local Codex access to supported Nanoleaf controls while preserving the selected installation's state ownership and explicit acceptance boundaries.

## Requirements

### Requirement: Explicit authenticated local hosting
The integration SHALL expose an opt-in loopback MCP host using the immutable shared module, fixed server-configured targets and current machine credentials. It SHALL run beside the Linux installation without a standalone hub or new remote ingress. This maps to issue #33 criteria 1, 2, 5, 6 and 7 and to [issue #131](https://github.com/jimmie-potts/codex-nanoleaf/issues/131) AC3.

#### Scenario: Native initialization and scoped discovery
- **WHEN** a native client initializes using a current machine credential and no Origin
- **THEN** the shared handler authenticates it and discovery contains only the configured target's tools allowed by its current scopes
- **AND** the tool surface exposes no power, brightness, zone or raw command, whatever the controller advertises
- **AND** the scene listing and scene activation tools each appear only for a credential holding their matching read or control scope

#### Scenario: Invalid transport or revoked principal
- **WHEN** the path, Host, supplied Origin or credential is invalid, or a principal is removed before new dispatch
- **THEN** the call is rejected before controller dispatch
- **AND** ordinary hooks, wall editor and worker remain unaffected

### Requirement: Fixed status and mode delegation
The tools SHALL expose only pure status and Work/Quiet/Free mode intent through the protected controller API. The host SHALL validate input and output with the released shared contract and SHALL preserve the existing designated worker's ownership. This maps to issue #33 criteria 1 through 4.

#### Scenario: Pure status and exact mode request
- **WHEN** status or discovery is requested
- **THEN** no task state is reserved, advanced or written and no light work is submitted
- **WHEN** a valid mode request is submitted
- **THEN** its request ID and expected revisions are passed unchanged to the fixed controller/device through `mode.set`
- **AND** the controller's valid receipt, including cancelled no-op and unknown observation evidence, is preserved without claiming visible output

#### Scenario: Caller selects an unsupported destination or operation
- **WHEN** tool arguments include a target override, raw URL, file path, unknown field or unsupported operation
- **THEN** validation rejects the call before any effect

### Requirement: Principal identity and bounded recovery
Each MCP principal SHALL use a distinct configured upstream controller credential. The host SHALL NOT forward incoming bearer tokens, create a replay ledger or automatically retry commands. It SHALL preserve request identity, controller failure semantics and possible prior effects. This maps to issue #33 criteria 4, 5 and 8.

#### Scenario: Duplicate, conflicting or stale request
- **WHEN** callers submit duplicate, conflicting or stale identities concurrently
- **THEN** the existing controller decides replay, conflict, generation and revision outcomes
- **AND** the MCP host preserves the returned receipt or rejection without allocating replacement identities

#### Scenario: Delivery ends after possible admission
- **WHEN** cancellation, disconnect, timeout, helper failure or invalid output occurs after a write may have dispatched
- **THEN** controller work remains independently owned and any delivered failure retains the original request ID and possible prior effects
- **AND** reconnect causes no command retry

#### Scenario: Credential replacement
- **WHEN** the private credential document changes or becomes unavailable
- **THEN** new authentication and dispatch use its current valid principal/scopes or reject
- **AND** a removed or downgraded principal cannot obtain control through an existing session

### Requirement: Immutable source qualification and acceptance boundary
The source SHALL pin and verify the released shared package, provide the Linux client template and qualify both supported MCP versions with fake-controller protocol tests. Installation and physical acceptance SHALL remain separately authorized, as recorded for the Linux fresh install in #55. This maps to issue #33 criteria 7 and 8.

#### Scenario: Isolated consumer validation
- **WHEN** the source is installed and tested without sibling repositories, personal credentials or devices
- **THEN** the vendored artifact, installed manifest and shared contract validate and real protocol fixtures cover the loopback route and qualified versions

#### Scenario: Source handoff
- **WHEN** source checks pass
- **THEN** the handoff reports source revision and test evidence separately from unperformed installed Codex, deployment and physical-light observations

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

### Requirement: Scoped scene discovery and Free-only activation
The host SHALL expose a read tool that lists the controller's advertised saved scenes with their opaque IDs and Nanoleaf app names, and a control tool, `nanoleaf_scene_activate`, that sends one `scene.activate` command through the protected controller, passing the caller's request ID and expected revisions through unchanged. Activation SHALL remain a separate command from mode selection; the tool SHALL NOT switch the device to Free itself. This maps to issue #91.

#### Scenario: Listing advertised scenes
- **WHEN** a credential with the read scope calls the scene listing tool
- **THEN** the result lists each advertised scene's opaque ID and, when present, its Nanoleaf app name
- **AND** no other field of the controller's extension snapshot is exposed and no task state is reserved, advanced or written

#### Scenario: Activation in Free
- **WHEN** a credential with the control scope activates an advertised scene while the device is in Free mode
- **THEN** the request ID and expected revisions are passed unchanged to the controller through `scene.activate`
- **AND** the controller's valid receipt, including a cancelled no-op and unknown observation evidence, is preserved without claiming visible output

#### Scenario: Rejection outside Free
- **WHEN** scene activation is requested while the device is in Work or Quiet mode
- **THEN** the tool returns the controller's typed `unsupported-capability` rejection with its replayable receipt
- **AND** the tool performs no mode switch of its own before or after the rejection

#### Scenario: Unknown scene identity
- **WHEN** the supplied scene ID does not match a scene currently advertised by the controller
- **THEN** the call is rejected before any device dispatch, typed the same as an unsupported capability

#### Scenario: Scope-mismatched or revoked credential
- **WHEN** a credential lacks the scene tool's required scope, or its scope is revoked before dispatch
- **THEN** the call is rejected before the controller is reached and no upstream request is sent
