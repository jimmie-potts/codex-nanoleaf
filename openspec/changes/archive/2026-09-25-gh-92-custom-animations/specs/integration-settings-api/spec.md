## MODIFIED Requirements

### Requirement: Separate finite extension contract
The API SHALL publish a Nanoleaf-owned versioned extension with strict requests and Python/TypeScript fixtures, leaving released shared v1 unchanged. Its matrix SHALL cover Work/Quiet/Free through existing v1, Classic/Project, whole/status coverage, reservations and half choices, task-project overrides and saved colors. Power, brightness and scene activation SHALL be served by shared v1 commands, not by extension operations; the extension SHALL only name discovered scenes. The extension's only light operation SHALL be the Free-only `animation.play` command. Locate, preview, source switching and unqualified devices SHALL be unsupported. This requirement also maps to [issue #64](https://github.com/jimmie-potts/codex-nanoleaf/issues/64) AC1 and [issue #92](https://github.com/jimmie-potts/codex-nanoleaf/issues/92) scope 1.

#### Scenario: Unsupported command
- **WHEN** a client requests preview, a general lighting operation other than `animation.play` or an unknown operation through the extension
- **THEN** the extension rejects it without sending a device command or widening shared v1

## ADDED Requirements

### Requirement: Validated Free-only animation command
The extension SHALL accept `animation.play` with a pattern from `wave`, `pulse`, `breathe`, `sparkle` and `gradient`, 1 to 8 `#rrggbb` colors, an optional speed (`slow`, `medium`, `fast`), an optional direction (`left`, `right`, `up`, `down`, `outward`, `inward`) that is allowed only for the spatial `wave` and `gradient` patterns, and an optional loop flag. The controller SHALL validate the command, current extension revision, desired Free mode and the encoded effect for the configured Lines before queueing. The encoded effect SHALL have at most 20 frames per zone and an 8,192-byte request body, below the 9,009-byte comet effect verified on the device. A rejection SHALL consume no request ticket and SHALL NOT write to the device. Maps to issue #92 scope 1, 3 and 5 and its validation and Free/Work/Quiet criteria.

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

### Requirement: Animation transport evidence
An animation receipt SHALL end as `sent` (prior effects `confirmed-transmission`), `failed` or `cancelled` (prior effects `none`), or `uncertain` (prior effects `possible`), always with `physicalOutcome` `unknown`. Identical duplicates SHALL join or replay the original receipt. Any explicit mode command, owner cancellation, credential revocation, controller disable and 30-second expiry SHALL retire a queued animation before it is sent. The worker SHALL record the attempt before its single device write and SHALL NEVER send an attempted animation again. Maps to issue #92 scope 3.

#### Scenario: Mode command retires a queued animation
- **WHEN** a Work, Quiet or Free mode command commits while an animation is queued
- **THEN** the animation is cancelled with `stale-generation` and no device write

#### Scenario: Interrupted send
- **WHEN** the device write raises or the worker stops after recording the attempt
- **THEN** the receipt ends `uncertain` with possible prior effects and no later pass sends it again

### Requirement: Animation discovery route
A read-scoped route SHALL return the supported patterns with their spatial flag, speeds, directions, defaults and limits, together with the current desired mode, extension revision and next request ticket, in one pure read transaction. The extension snapshot's shape, capabilities and limits SHALL remain unchanged. Maps to issue #92 scope 4.

#### Scenario: Reading animation options
- **WHEN** a read-scoped credential reads the animation route
- **THEN** it receives the fixed option set and the identity values needed to play, the database bytes are unchanged and no device is contacted
- **AND** the extension snapshot does not list `animation.play`
