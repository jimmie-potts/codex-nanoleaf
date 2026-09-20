## Purpose

Allow native machine consumers to inspect and edit existing Nanoleaf task-display settings without exposing private metadata or becoming a light writer. Scope is [issue #49](https://github.com/jimmie-potts/codex-nanoleaf/issues/49).

## Requirements

### Requirement: Separate finite extension contract
The API SHALL publish a Nanoleaf-owned versioned extension with strict requests and Python/TypeScript fixtures, leaving released shared v1 unchanged. Its matrix SHALL cover Work/Quiet/Free through existing v1, Classic/Project, whole/status coverage, reservations and half choices, task-project overrides and saved colors. Locate, preview, general lighting, source switching and unqualified devices SHALL be unsupported.

#### Scenario: Unsupported command
- **WHEN** a client requests preview or an unknown operation
- **THEN** the extension rejects it without sending a device command or widening shared v1

### Requirement: Pure private projection
Reads SHALL provide the configured device, stable physical element IDs, opaque local identities and qualified shared mappings, current configuration, pending edits and bounded outcomes in one read transaction. Reads SHALL exclude paths, automatic titles, credentials and raw provider metadata and SHALL NOT refresh metadata, initialize state, clear notices, mark tasks read, advance effects or launch work.

#### Scenario: Private inspection
- **WHEN** private paths and titles exist and a client reconnects or inspects an element
- **THEN** the returned allowlisted projection excludes them and leaves database bytes and device activity unchanged

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
The extension SHALL support current Lines on native Linux and retained Windows ownership/forwarding. Documentation SHALL specify versioning and rollback that preserve current databases. Source fixtures SHALL remain separate from installed-client and physical acceptance.

#### Scenario: Version rollback
- **WHEN** an operator returns to source without the extension
- **THEN** existing v1 operations remain compatible, and documented cancellation and listener shutdown prevent stale extension work from replaying on later upgrade
