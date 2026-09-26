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
Accepted wall-configuration edits through the extension SHALL use the same application operations as the wall, on the installation's private native-OS database. Machine-only favorite edits SHALL use the extension's private recipe operations and the same worker transaction. All extension edits SHALL preserve input selection, scene state, notices, task/effect epochs and unrelated reservations and pending edits. Only the existing worker SHALL send light updates. Active comet source reservations SHALL remain until their existing completion boundary.

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

### Requirement: Read-only element geometry route
A read-scoped route SHALL return, for any configured device, that device's identity, layout kind and elements in the saved order. Each element SHALL carry its stable element ID, element number, ordered zone IDs and the display points the wall map draws, with the controller's global orientation and Y inversion applied: three points along a Line or the three vertices of a triangle. For the Lines, the response SHALL also carry the connector graph when the saved layout supports it. A device with no saved layout entry SHALL return an explicit empty result; a saved layout without drawable geometry SHALL list its elements with null points. The route SHALL read only the saved layout and one SQLite read transaction, SHALL NOT discover geometry, contact a device, write state or change the extension snapshot's shape, and SHALL carry no address, credential or private path. An unknown device SHALL fail as it does for the extension snapshot. Maps to [issue #169](https://github.com/jimmie-potts/codex-nanoleaf/issues/169) scope and its fake-device and hub-consumer criteria.

#### Scenario: Reading the Lines geometry
- **WHEN** a read-scoped credential reads the geometry route for the Lines with a saved layout and connector geometry
- **THEN** it receives each Line's ID, number, zone pair and three display points in the saved order, plus the connector graph, the database bytes are unchanged and no device is contacted

#### Scenario: Reading the Panels geometry
- **WHEN** a client reads the geometry route for the configured Panels
- **THEN** it receives each triangle's ID, number, panel zone and three vertices in the saved order, with no connector graph

#### Scenario: Device without a saved layout
- **WHEN** a client reads the geometry route for a configured device that has no saved layout entry
- **THEN** it receives the device identity with a null kind, no elements and no connectors

#### Scenario: Unknown device
- **WHEN** a client reads the geometry route naming a device that is not configured
- **THEN** the request fails with the same failure code the extension snapshot returns for that device

### Requirement: Remembered scene discovery

The animation options route SHALL expose rememberedSceneId as the existing opaque ID of the saved scene only while that name remains advertised; otherwise it SHALL be null. This read SHALL leave saved scene, brightness, task state and both snapshot shapes unchanged.

Maps to [issue #150](https://github.com/jimmie-potts/codex-nanoleaf/issues/150) source acceptance.

#### Scenario: Remembered advertised scene

- **WHEN** animation options are read and the saved scene is advertised
- **THEN** rememberedSceneId matches that scene's shared v1 opaque ID without a device request or state write

#### Scenario: Missing or disappeared scene

- **WHEN** saved scene state is missing, unreadable, has no scene, or names a scene no longer advertised
- **THEN** rememberedSceneId is null and no scene is chosen or written

### Requirement: Named animation presets
The controller SHALL advertise the ten curated moods from issue #153 as `presets` in the animation options route, with each `id`, pattern, colors, speed and applicable direction. An `animation.play` command SHALL accept either existing explicit parameters or only `preset` with an advertised name. The server SHALL resolve a preset to the same encoded frames as the equivalent explicit request, retain the original request for replay, and preserve Free-only admission, frame and byte limits, receipts and the integration snapshot shape.

#### Scenario: Inspect and play a mood
- **WHEN** a caller lists options then submits a preset-only request while in Free
- **THEN** the existing worker sends the same effect as the listed explicit fields, within the existing bounds
- **AND** replay uses the unchanged original request and receipt

#### Scenario: Reject ambiguous or unavailable preset requests
- **WHEN** the name is unknown, explicit fields accompany the name, mode is Work or Quiet, or the layout cannot encode the effect
- **THEN** the existing validation or typed admission failure rejects the request before a light write

### Requirement: Private persistent animation favorites

The extension SHALL store at most 32 named favorites in private installation SQLite. `animation.save` SHALL take `name` and `animation` (explicit play fields without `kind`, or a named preset), freeze all applicable defaults, and reject an occupied name without replacing data. `animation.rename` SHALL take `name` and `newName`, atomically move an existing recipe, and reject an occupied target without changing either entry. `animation.forget` SHALL delete the named existing recipe. Names SHALL be case-sensitive, 1–80 Unicode characters, nonblank and free of control characters, with no silent trimming. Missing names SHALL fail as `unsupported-capability`; collisions SHALL fail as `revision-conflict`; exceeding 32 entries SHALL fail as `capacity`. Configuration operations SHALL preserve the current mode and use existing extension authorization, tickets, revisions, queue, replay, cancellation, expiry, and atomic `applied` receipts with `priorEffects: configuration`. They SHALL NOT send light commands or clear a transport hold. Maps to [issue #154](https://github.com/jimmie-potts/codex-nanoleaf/issues/154) persistence, save/delete, collision and bound criteria and the approved rename decision.

#### Scenario: Save and reopen
- **WHEN** a client saves supplied fields or a preset and the worker applies the command
- **THEN** the complete recipe survives database reopen and repeated initialization, with omitted defaults frozen and no change to the selected mode

#### Scenario: Collision preserves recipes
- **WHEN** a save names an existing favorite or a rename targets an occupied name
- **THEN** it fails without consuming a ticket or changing either recipe

#### Scenario: Configuration in every mode
- **WHEN** an authorized client saves, renames or forgets a favorite in Work, Quiet or Free
- **THEN** the existing worker commits configuration and its receipt together without an attributed transport write

### Requirement: Private favorite discovery and playback

The authenticated animation options route SHALL include named favorite recipes and their count/name bounds. Favorite data SHALL be excluded from browser projections and the Hub's extension snapshot. The extension snapshot SHALL retain its exact shape. Favorite changes SHALL invalidate the extension revision. `animation.play` SHALL accept `favorite` as an exclusive alternative to explicit fields or `preset`; playback SHALL retain Free-only admission, bounds checked against the current layout, transport receipts, cancellation, and the single existing device writer. Maps to issue #154 replay, privacy, frame/byte bounds and snapshot criteria.

#### Scenario: Replay the saved recipe
- **WHEN** an authorized client plays a favorite in Free
- **THEN** the worker sends the same encoded effect as its saved complete explicit recipe, within current frame and byte bounds

#### Scenario: Pure private discovery
- **WHEN** a read principal lists animation options
- **THEN** it sees the bounded favorites without database mutation, worker launch, device access, or disclosure in browser or Hub snapshot data
