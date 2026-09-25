## Purpose

Allow native machine consumers to inspect and edit existing Nanoleaf task-display settings, and to request Free-mode animations that the existing worker plays, without exposing private metadata or becoming a light writer. Scope is [issue #49](https://github.com/jimmie-potts/codex-nanoleaf/issues/49); [issue #92](https://github.com/jimmie-potts/codex-nanoleaf/issues/92) adds animations.

## Requirements

### Requirement: Separate finite extension contract
The API SHALL publish a Nanoleaf-owned versioned extension with strict requests and Python/TypeScript fixtures, leaving released shared v1 unchanged. Its matrix SHALL cover Work/Quiet/Free through existing v1, Classic/Project, whole/status coverage, reservations and half choices, task-project overrides and saved colors. Power, brightness and scene activation SHALL be served by shared v1 commands, not by extension operations; the extension SHALL only name discovered scenes. The extension's only light operation SHALL be the Free-only `animation.play` command. Locate, preview, source switching and unqualified devices SHALL be unsupported. This requirement also maps to [issue #64](https://github.com/jimmie-potts/codex-nanoleaf/issues/64) AC1 and [issue #92](https://github.com/jimmie-potts/codex-nanoleaf/issues/92) scope 1.

#### Scenario: Unsupported command
- **WHEN** a client requests preview, a general lighting operation other than `animation.play` or an unknown operation through the extension
- **THEN** the extension rejects it without sending a device command or widening shared v1

### Requirement: Pure private projection
Reads SHALL provide the configured device, stable physical element IDs, opaque local identities and qualified shared mappings, current configuration, pending edits, bounded outcomes and the discovered saved scenes as opaque IDs with their user-chosen Nanoleaf names, in one read transaction. A name SHALL be present only when the device reported it within the shared 80-character label bound; nothing else is copied into names. Reads SHALL exclude paths, automatic titles, credentials and raw provider metadata and SHALL NOT refresh metadata, initialize state, clear notices, mark tasks read, advance effects, launch work or call the device.

#### Scenario: Private inspection
- **WHEN** private paths and titles exist and a client reconnects or inspects an element
- **THEN** the returned allowlisted projection excludes them and leaves database bytes and device activity unchanged

#### Scenario: Scene names travel only through the extension
- **WHEN** the worker has observed saved scenes and a client reads both the shared snapshot and the extension snapshot
- **THEN** the shared snapshot advertises only opaque scene IDs, the extension lists the same IDs with their user-chosen names, and neither read contacts the device

### Requirement: Scoped revisioned admission
Writes SHALL require native machine control authority, explicit configured target, extension request identity and a current configuration/assignment revision. Authentication and principal/target scope SHALL precede replay. Identical duplicates SHALL join or replay the original result, conflicting reuse SHALL fail, and expired IDs SHALL NOT execute again. Bounds SHALL cover body size, queue, retained receipts and projection size.

#### Scenario: Concurrent edits
- **WHEN** a wall or native edit changes the expected configuration or assignment revision before an extension edit applies
- **THEN** the edit returns or becomes a conflict without overwriting the newer state

### Requirement: Preserve state through application operations
Accepted extension edits SHALL use the same application operations as the wall, on the installation's private native-OS database. They SHALL preserve input selection, scene state, notices, task/effect epochs and unrelated reservations and pending edits. Only the existing worker SHALL send light updates. Active comet source reservations SHALL remain until their existing completion boundary.

#### Scenario: Deferred reservation
- **WHEN** an assignment arrives during an active comet or an existing wall edit is pending
- **THEN** it remains bounded pending or fails with an actionable conflict, preserving both existing work and the comet source

### Requirement: Explicit recovery and configuration evidence
The extension SHALL distinguish queued, applied configuration, failed and cancelled results, recording prior configuration effects and unknown physical outcomes. Owner cancellation, credential revocation, expiry and superseding edits SHALL prevent unapplied work from executing. Lost responses SHALL be resolved through read-only receipt lookup; reconnect SHALL NOT retry writes automatically.

#### Scenario: Cancel and recover
- **WHEN** a queued edit is cancelled or its credential revoked, or an applied response is lost
- **THEN** unapplied work does not execute and retained receipts distinguish no effects from committed configuration without claiming visible output

### Requirement: Portable bounded delivery
The extension SHALL support current Lines on the native Linux installation. Documentation SHALL specify versioning and rollback that preserve current databases. Source fixtures SHALL remain separate from installed-client and physical acceptance. This requirement also maps to [issue #131](https://github.com/jimmie-potts/codex-nanoleaf/issues/131) AC6.

#### Scenario: Version rollback
- **WHEN** an operator returns to source without the extension
- **THEN** existing v1 operations remain compatible, and documented cancellation and listener shutdown prevent stale extension work from replaying on later upgrade

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
An animation receipt SHALL end as `sent` (prior effects `confirmed-transmission`), `failed` or `cancelled` (prior effects `none`), or `uncertain` (prior effects `possible`), always with `physicalOutcome` `unknown`. Identical duplicates SHALL join or replay the original receipt. Any explicit mode command, owner cancellation, credential revocation, controller disable and 30-second expiry SHALL retire a queued animation before it is sent. Admitting an animation SHALL clear a controller transport hold and authorize another attempt, like a fresh v1 control; an animation whose worker launch fails or that expires unsent SHALL restore the hold, like unsent v1 work. The worker SHALL record the attempt before its single device write and SHALL NEVER send an attempted animation again. Maps to issue #92 scope 3.

#### Scenario: Mode command retires a queued animation
- **WHEN** a Work, Quiet or Free mode command commits while an animation is queued
- **THEN** the animation is cancelled with `stale-generation` and no device write

#### Scenario: Interrupted send
- **WHEN** the device write raises or the worker stops after recording the attempt
- **THEN** the receipt ends `uncertain` with possible prior effects and no later pass sends it again

#### Scenario: Animation after a held machine request
- **WHEN** an earlier machine request left the installation held and an animation is admitted in Free
- **THEN** the hold is cleared, the worker plays the animation, and the earlier uncertain request is not sent again

### Requirement: Animation discovery route
A read-scoped route SHALL return the supported patterns with their spatial flag, speeds, directions, defaults and limits, together with the current desired mode, extension revision and next request ticket, in one pure read transaction. The extension snapshot's shape, capabilities and limits SHALL remain unchanged. Maps to issue #92 scope 4.

#### Scenario: Reading animation options
- **WHEN** a read-scoped credential reads the animation route
- **THEN** it receives the fixed option set and the identity values needed to play, the database bytes are unchanged and no device is contacted
- **AND** the extension snapshot does not list `animation.play`

### Requirement: Read-only extension for other devices
For a configured device other than the original Lines, the extension SHALL be read-only. Its snapshot SHALL keep the extension's exact key set, carry that device's identity, configuration revision, mode and discovered scenes, list no elements, pending wall edit or requests, and mark every configuration operation unsupported. Extension commands for that device, including `animation.play`, SHALL fail with `unsupported-capability` before any reservation or effect. Receipt and cancel lookups under that device SHALL return `request-expired`, and its animation discovery route SHALL return `unsupported-capability`. Shared configuration, element assignment and animations SHALL stay with the original Lines ledger. This requirement maps to [issue #113](https://github.com/jimmie-potts/codex-nanoleaf/issues/113) scope 1.

#### Scenario: Reading the Panels extension snapshot
- **WHEN** the worker has observed the Panels' saved scenes and a client reads the extension snapshot for the Panels
- **THEN** it returns the Panels' identity, revision, mode and named scenes, no elements, and unsupported configuration operations, without contacting either device

#### Scenario: Extension command for the Panels
- **WHEN** a client sends `project.color` or `animation.play` to the extension naming the Panels
- **THEN** the request fails with `unsupported-capability`, no request identity is consumed, and neither device receives a write
