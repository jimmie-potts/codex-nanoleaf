## ADDED Requirements

### Requirement: Requested animation playback
The original Lines instance SHALL play a queued extension animation only while its mode is Free, as one journaled `PUT /effects` display write through its existing light transport, with no per-frame streaming and no brightness or power write. A pending mode command SHALL apply first; queued v1 controls and animations SHALL then run oldest first by admission. The worker SHALL encode status and animation effects with one shared frame encoder, and status payloads SHALL stay byte-identical. Every pattern SHALL use the saved Lines geometry, give both zones of a Line the same frames and stay within the extension's frame and byte bounds. Panels instances SHALL never play extension animations. Maps to [issue #92](https://github.com/jimmie-potts/codex-nanoleaf/issues/92) scope 2 and 3 and its encoder criterion.

#### Scenario: Animation after the Free handoff
- **WHEN** a Free mode command and an animation are both pending in one pass
- **THEN** the Free handoff write happens first, the animation's display write follows, and the animation receipt ends `sent`

#### Scenario: Pattern encoding on fixture layouts
- **WHEN** each pattern renders on the 15-Line fixture and a two-Line layout
- **THEN** every zone gets a positive-duration frame list within 20 frames, paired zones match, spatial patterns order their phases along the requested direction, and the request body is at most 8,192 bytes

#### Scenario: Status encoding unchanged
- **WHEN** a status display is encoded through the shared encoder
- **THEN** its payload equals the payload produced before the encoder was extracted
