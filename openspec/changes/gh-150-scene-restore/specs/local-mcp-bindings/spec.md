## ADDED Requirements

### Requirement: Explicit remembered scene restore

The Lines-only nanoleaf_scene_restore tool SHALL require control scope, accept the caller's shared v1 request identity and revisions, read rememberedSceneId from animation options and send exactly one existing scene.activate through the activation handler. It SHALL never switch mode, retry, write scene state or change remembered brightness.

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
