## MODIFIED Requirements

### Requirement: Separate finite extension contract
The API SHALL publish a Nanoleaf-owned versioned extension with strict requests and Python/TypeScript fixtures, leaving released shared v1 unchanged. Its matrix SHALL cover Work/Quiet/Free through existing v1, Classic/Project, whole/status coverage, reservations and half choices, task-project overrides and saved colors. Power, brightness and scene activation SHALL be served by shared v1 commands, not by extension operations; the extension SHALL only name discovered scenes. Locate, preview, source switching and unqualified devices SHALL be unsupported. This requirement also maps to [issue #64](https://github.com/jimmie-potts/codex-nanoleaf/issues/64) AC1.

#### Scenario: Unsupported command
- **WHEN** a client requests preview, a general lighting operation or an unknown operation through the extension
- **THEN** the extension rejects it without sending a device command or widening shared v1

### Requirement: Pure private projection
Reads SHALL provide the configured device, stable physical element IDs, opaque local identities and qualified shared mappings, current configuration, pending edits, bounded outcomes and the discovered saved scenes as opaque IDs with their user-chosen Nanoleaf names, in one read transaction. A name SHALL be present only when the device reported it within the shared 80-character label bound; nothing else is copied into names. Reads SHALL exclude paths, automatic titles, credentials and raw provider metadata and SHALL NOT refresh metadata, initialize state, clear notices, mark tasks read, advance effects, launch work or call the device.

#### Scenario: Private inspection
- **WHEN** private paths and titles exist and a client reconnects or inspects an element
- **THEN** the returned allowlisted projection excludes them and leaves database bytes and device activity unchanged

#### Scenario: Scene names travel only through the extension
- **WHEN** the worker has observed saved scenes and a client reads both the shared snapshot and the extension snapshot
- **THEN** the shared snapshot advertises only opaque scene IDs, the extension lists the same IDs with their user-chosen names, and neither read contacts the device
