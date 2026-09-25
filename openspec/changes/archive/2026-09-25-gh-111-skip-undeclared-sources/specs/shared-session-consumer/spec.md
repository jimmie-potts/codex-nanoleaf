## MODIFIED Requirements

### Requirement: Validated bounded shared input
The consumer SHALL request snapshot 1.1, require a non-negative safe integer generation no greater than its revision for every session, and validate the versioned snapshot contract and expected owner over authenticated configured numeric-loopback HTTP with bounded time, size and concurrency, no redirects and no proxy use. Source readiness declarations SHALL distinguish operator assertions from verified feed evidence. No provider reducer SHALL be copied to Python. A session whose provider, client, host and source are not declared in the configuration SHALL be skipped rather than rejecting the snapshot: it SHALL receive no Line, wave, comet or acknowledgment and SHALL take no part in parent and subagent grouping, while declared sessions keep updating. This covers #29 shared-contract, privacy and transport criteria and #111 undeclared sources.

#### Scenario: Invalid or unavailable host
- **WHEN** authentication fails, input exceeds bounds, a version/owner/schema is invalid, or a revision regresses
- **THEN** the last valid projection remains with stale/unavailable health and fixed diagnostics, no raw response/credential disclosure and no automatic fallback

#### Scenario: Multiple identities
- **WHEN** concurrent sessions share a project or raw session ID but differ in full source identity
- **THEN** they remain distinct and only explicit bindings connect them to retained local presentation identities
- **AND** Codex sessions may resolve local title and project metadata by provider and raw session ID without merging identities or creating lifecycle state

#### Scenario: Undeclared source among declared sessions
- **WHEN** a valid snapshot contains sessions from a source missing from the declared sources alongside declared sessions
- **THEN** only the declared sessions are presented and keep updating, and the connection stays current
- **AND** a snapshot containing only undeclared sessions leaves the wall without shared tasks and the connection current

#### Scenario: Undeclared parent of a declared subagent
- **WHEN** a declared session's evidenced parent is skipped
- **THEN** the declared session follows the existing missing-parent rule and a skipped session never contributes to a declared task

#### Scenario: Source declared later
- **WHEN** the operator declares a source whose sessions already exist in the feed and selects shared input again
- **THEN** those sessions appear in their current state without replaying earlier outward waves or completion comets

### Requirement: Pure sanitized inspection and private ownership
Inspection SHALL report source selection, owner, consumer health and sanitized identity/project mapping without starting a worker, changing state, contacting a device or returning credentials/private metadata. Inspection SHALL also report how many sessions the last projection skipped and their distinct source identities. One installation-local Python worker SHALL remain the sole device writer; SQLite SHALL remain private to its operating system. This covers #29 additional health and runtime criteria and #111 skipped-source visibility.

#### Scenario: Inspect integration state
- **WHEN** a caller reads shared status
- **THEN** it receives selected source, neutral identities, connection, last revision/update, evidence age, uncertainty and fixed errors without mutations or credential/path disclosure

#### Scenario: Inspect skipped sources
- **WHEN** the last projection skipped sessions from undeclared sources
- **THEN** shared status reports the skipped session count and each distinct skipped source identity, so a missing declaration is visible
