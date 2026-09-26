## ADDED Requirements

### Requirement: Remembered scene discovery

The animation options route SHALL expose rememberedSceneId as the existing opaque ID of the saved scene only while that name remains advertised; otherwise it SHALL be null. This read SHALL leave saved scene, brightness, task state and both snapshot shapes unchanged.

#### Scenario: Remembered advertised scene

- **WHEN** animation options are read and the saved scene is advertised
- **THEN** rememberedSceneId matches that scene's shared v1 opaque ID without a device request or state write

#### Scenario: Missing or disappeared scene

- **WHEN** saved scene state is missing, unreadable, has no scene, or names a scene no longer advertised
- **THEN** rememberedSceneId is null and no scene is chosen or written
