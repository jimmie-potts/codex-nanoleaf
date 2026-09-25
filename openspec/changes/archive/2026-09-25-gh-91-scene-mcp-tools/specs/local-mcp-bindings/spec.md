## MODIFIED Requirements

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

## ADDED Requirements

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
