## ADDED Requirements

### Requirement: Explicit remembered scene restore

The Lines-only nanoleaf_scene_restore tool SHALL require control scope, accept the caller's shared v1 request identity and revisions, read rememberedSceneId from animation options and send exactly one existing scene.activate through the activation handler. It SHALL never switch mode, retry, write scene state or change remembered brightness.

Maps to [issue #150](https://github.com/jimmie-potts/codex-nanoleaf/issues/150) source acceptance.

#### Scenario: Restore in Free

- **WHEN** the caller restores an advertised remembered scene in Free
- **THEN** exactly one scene.activate preserves the supplied requestId, expectedConfigurationRevision and expectedGeneration and returns the existing controller receipt

#### Scenario: Mode forbids restoration

- **WHEN** the options report Work or Quiet
- **THEN** the tool returns unsupported-capability with a message to switch to Free and dispatches no command

#### Scenario: No remembered target

- **WHEN** rememberedSceneId is null
- **THEN** the tool returns unsupported-capability with priorEffects none and no dispatch

#### Scenario: Authority changes or transport fails

- **WHEN** credentials change after discovery or command delivery becomes uncertain
- **THEN** dispatch rechecks authority and retains the existing typed failure, receipt and no-retry semantics

## MODIFIED Requirements

### Requirement: Optional fixed Panels target
When the private configuration names `panelsDeviceId`, the host SHALL bind that device as a second fixed target with `nanoleaf_panels_status`, `nanoleaf_panels_mode_set`, `nanoleaf_panels_scenes_list` and `nanoleaf_panels_scene_activate`. They follow the same scopes, validation, receipts and failure handling as the Lines tools. The Panels tools SHALL always address only the configured Panels device, and the Lines tools only the configured Lines device. No tool SHALL accept a device argument. Without `panelsDeviceId`, the tool surface SHALL be unchanged. Animation tools SHALL remain Lines-only. This requirement maps to [issue #113](https://github.com/jimmie-potts/codex-nanoleaf/issues/113) scope 4.

#### Scenario: Discovery with a Panels target
- **WHEN** the configuration names `panelsDeviceId` and a control-scope client lists tools
- **THEN** discovery contains the configured Lines tools and the four Panels tools, and no Panels animation tool

#### Scenario: Panels mode request
- **WHEN** a client calls `nanoleaf_panels_mode_set` with a valid request identity
- **THEN** the controller receives a `mode.set` request naming the Panels device, and the Lines tools' requests still name the Lines

#### Scenario: Device override attempt
- **WHEN** a client passes a `deviceId` argument to any tool
- **THEN** validation rejects the call before controller dispatch

#### Scenario: No Panels target configured
- **WHEN** the configuration has no `panelsDeviceId`
- **THEN** discovery and behavior match the existing Lines-only host
