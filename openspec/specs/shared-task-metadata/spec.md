# Shared task metadata

## Purpose

Keep shared Codex tasks recognizable and correctly assigned to local projects without changing shared lifecycle authority or exposing metadata upstream.

## Requirements

### Requirement: Local Codex presentation enrichment
The consumer SHALL enrich currently presented shared sessions whose provider is `codex` using their raw session identity and the configured local Codex metadata. Titles SHALL use a hub label, then local title, then fallback. Projects SHALL use a manual override, then hub project, then the existing local assignment and workspace-root matching rules. Other providers SHALL NOT receive Codex metadata. Local metadata SHALL remain read-only and SHALL NOT be uploaded to the hub. This implements #75.

#### Scenario: Local metadata arrives during shared monitoring
- **WHEN** a present Codex task has no hub label or project and its local metadata becomes available
- **THEN** its displayed title and allocation project update on polling, including when the shared revision is unchanged
- **AND** its lifecycle, freshness, turn and effect epochs remain unchanged

#### Scenario: Precedence and provider isolation
- **WHEN** a hub label and project, a local Codex match and a manual project preference coexist
- **THEN** the hub label is displayed and the manual project controls allocation
- **AND** a Claude task with the same raw session ID receives no Codex title or project

### Requirement: Distinct fallback names
A task without an available title SHALL display its provider name and the last eight hexadecimal characters of its raw session ID, such as `Codex 5b1e07c2` or `Claude 4227761b`. Legacy Codex tasks SHALL use the same fallback rule. IDs with fewer than eight hexadecimal characters SHALL use their available hexadecimal suffix, or the raw ID suffix when none exist.

#### Scenario: Nearby UUIDs without titles
- **WHEN** two tasks have UUIDs with the same timestamp prefix and different final eight hexadecimal characters
- **THEN** the map displays distinct provider-prefixed fallback titles in shared and legacy modes

### Requirement: Metadata does not own lifecycle
Metadata lookup SHALL enrich only tasks presented by the current shared snapshot. It SHALL NOT create, restore, renew or retain a retired shared task. Source switching and restart SHALL preserve manual preferences and use the selected source's presentation rules.

#### Scenario: Retired task remains in local metadata
- **WHEN** the owner removes a task while its local title and project remain available
- **THEN** polling and map reads do not recreate the task or reserve its Line

#### Scenario: Restart and rollback
- **WHEN** the consumer restarts in shared mode or switches back to legacy
- **THEN** metadata remains available under the selected source and manual preferences survive the existing explicit identity bindings
