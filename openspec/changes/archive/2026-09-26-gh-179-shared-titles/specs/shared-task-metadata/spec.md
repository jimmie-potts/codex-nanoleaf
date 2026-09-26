## MODIFIED Requirements

### Requirement: Local Codex presentation enrichment
The consumer SHALL enrich currently presented shared sessions whose provider is `codex` using their raw session identity and the configured local Codex metadata. Titles SHALL use a hub label, then the shared title value, then local Codex title, then fallback. Shared title and project fields SHALL apply to every declared provider. Projects SHALL use a manual override, then hub project, then the existing local assignment and workspace-root matching rules. Other providers SHALL NOT receive Codex metadata. The existing local Codex readers SHALL remain read-only fallbacks until shared coverage is verified. Tokens and credential paths SHALL remain excluded. This implements #75 and #179.

#### Scenario: Local metadata arrives during shared monitoring
- **WHEN** a present Codex task has no hub label, title or project and its local metadata becomes available
- **THEN** its displayed title and allocation project update on polling, including when the shared revision is unchanged
- **AND** its lifecycle, freshness, turn and effect epochs remain unchanged

#### Scenario: Precedence and provider isolation
- **WHEN** a hub label and project, a local Codex match and a manual project preference coexist
- **THEN** the hub label is displayed and the manual project controls allocation
- **AND** a Claude task with the same raw session ID receives no Codex title or project

#### Scenario: Shared metadata reaches the wall
- **WHEN** a snapshot 1.2 task has a title and project name and no hub label
- **THEN** its context card displays that title and project name ahead of local metadata
- **AND** a hub label still wins and manual project preferences still control allocation

#### Scenario: Claude shared metadata without a local reader
- **WHEN** a declared Claude session has shared title and project fields
- **THEN** the wall uses them without reading a Claude transcript or inheriting Codex metadata
- **AND** absent shared metadata retains the provider fallback
