## ADDED Requirements

### Requirement: Wall links use the presented root identity
The wall task projection SHALL expose `codexUrl` only when its presented root session has provider `codex`, client `desktop` and a valid UUID session ID. Folded children SHALL NOT supply or replace that identity. The URL SHALL be built on the server and SHALL NOT enter controller or integration API projections or the shared feed. Eligibility SHALL NOT change session lifecycle, allocation or read state. Covers #108 AC2, AC3, AC4 and AC5.

#### Scenario: Desktop parent with folded child
- **WHEN** a shared Desktop root session has a folded child
- **THEN** its single wall task links to the parent's UUID, never the child's

#### Scenario: Ineligible root
- **WHEN** a root is Codex CLI, Claude Code, an unknown client, or has a malformed session ID
- **THEN** its wall task has no link even if a child is an eligible Desktop session or a matching ID exists in the local title index
