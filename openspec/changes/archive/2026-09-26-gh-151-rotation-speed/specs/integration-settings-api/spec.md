## MODIFIED Requirements

### Requirement: Validated Free-only animation command
The extension SHALL accept `animation.play` with a pattern from `wave`, `pulse`, `breathe`, `sparkle` and `gradient`, 1 to 8 `#rrggbb` colors, an optional speed (`slow`, `medium`, `fast`, `faster`), an optional direction (`left`, `right`, `up`, `down`, `outward`, `inward`, `clockwise`, `counterclockwise`) that is allowed only for the spatial `wave` and `gradient` patterns, and an optional loop flag. The controller SHALL validate the command, current extension revision, desired Free mode and the encoded effect for the configured Lines before queueing. The encoded effect SHALL have at most 20 frames per zone and an 8,192-byte request body, below the 9,009-byte comet effect verified on the device. A rejection SHALL consume no request ticket and SHALL NOT write to the device. Maps to issue #92 scope 1, 3 and 5 and its validation and Free/Work/Quiet criteria.

#### Scenario: Malformed or out-of-bounds animation
- **WHEN** a request has an unknown pattern, zero or nine colors, a malformed color, an unknown speed, a direction on `pulse`, `breathe` or `sparkle`, or an unknown field
- **THEN** it fails as `invalid-request` before admission and its ticket remains available

#### Scenario: Rejection in Work or Quiet
- **WHEN** a valid animation arrives while the desired mode is Work or Quiet
- **THEN** it fails as `unsupported-capability` before queueing, without a device write, a mode change or a consumed ticket

#### Scenario: Effect too large for the proven envelope
- **WHEN** the encoded effect for the configured Lines would exceed the frame or byte bound
- **THEN** it fails as `capacity` before queueing

#### Scenario: Accepted in Free
- **WHEN** a valid, current animation arrives while the desired mode is Free and no extension request is queued
- **THEN** it is queued under its ticket with a `queued` receipt and the worker is woken

#### Scenario: Rotating and faster options
- **WHEN** a client requests either spatial pattern with `clockwise` or `counterclockwise` and `faster`
- **THEN** validation accepts those values under the same Free-only admission and encoded bounds, and animation discovery lists them
- **AND** a rotation direction on a non-spatial pattern remains invalid

Maps to [issue #151](https://github.com/jimmie-potts/codex-nanoleaf/issues/151) validation and MCP acceptance.
