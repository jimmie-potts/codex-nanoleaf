## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Preserve state through application operations
Accepted wall-configuration edits through the extension SHALL use the same application operations as the wall, on the installation's private native-OS database. Machine-only favorite edits SHALL use the extension's private recipe operations and the same worker transaction. All extension edits SHALL preserve input selection, scene state, notices, task/effect epochs and unrelated reservations and pending edits. Only the existing worker SHALL send light updates. Active comet source reservations SHALL remain until their existing completion boundary.

#### Scenario: Deferred reservation
- **WHEN** an assignment arrives during an active comet or an existing wall edit is pending
- **THEN** it remains bounded pending or fails with an actionable conflict, preserving both existing work and the comet source
