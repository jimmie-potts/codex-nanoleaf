## MODIFIED Requirements

### Requirement: Animation discovery and Free-only playback
The host SHALL expose a read tool, `nanoleaf_animations_list`, that returns the controller's animation patterns, speeds, directions, defaults and limits with the current mode, extension revision and next request ticket, and a control tool, `nanoleaf_animation_play`, that sends one `animation.play` extension request built from the caller's request ticket, expected revision and animation fields. The tools SHALL expose the additive `clockwise`, `counterclockwise` and `faster` values. The play tool SHALL NOT switch mode itself. It SHALL validate every field against the fixed bounds before dispatch and SHALL return only a receipt whose ticket matches the request. A Work or Quiet rejection SHALL tell the caller to switch to Free with `nanoleaf_mode_set` and read the list again. Maps to [issue #92](https://github.com/jimmie-potts/codex-nanoleaf/issues/92) scope 4 and its MCP criterion.

#### Scenario: Listing animation options
- **WHEN** a read-scoped credential calls `nanoleaf_animations_list`
- **THEN** the result carries the option set and identity values from the controller's animation route and no task state is reserved, advanced or written

#### Scenario: Playing in Free
- **WHEN** a control-scoped credential plays a valid animation while the device is in Free
- **THEN** the ticket, revision and fields reach the controller unchanged and the queued receipt is returned without claiming visible output

#### Scenario: Rejection outside Free
- **WHEN** the controller rejects the animation because the device is in Work or Quiet
- **THEN** the tool returns the typed `unsupported-capability` failure with a message to switch to Free first, and performs no mode switch

#### Scenario: Invalid animation fields
- **WHEN** the call has an unknown pattern, too many colors, a malformed color, or a direction on a non-spatial pattern
- **THEN** it is rejected before any controller dispatch

#### Scenario: Scope-mismatched credential
- **WHEN** a credential lacks the animation tool's required scope
- **THEN** discovery omits that tool and a dispatch never reaches the controller

#### Scenario: Rotating and faster tool options
- **WHEN** a client discovers and calls the animation tools
- **THEN** the play schema and listing include `clockwise`, `counterclockwise` and `faster`, and a valid call forwards those values unchanged

Maps to [issue #151](https://github.com/jimmie-potts/codex-nanoleaf/issues/151) validation and MCP acceptance.
