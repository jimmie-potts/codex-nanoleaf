## ADDED Requirements

### Requirement: Named mood inputs
The MCP animation listing SHALL include the server's curated preset definitions. Animation play SHALL accept a preset name instead of explicit animation fields and forward that name unchanged, without defaults or overrides. Existing scopes, Free-only controls and receipt semantics SHALL remain unchanged.

#### Scenario: List and play a preset
- **WHEN** a permitted client lists animations and plays one named preset
- **THEN** the listing includes the preset's explicit parameters and one preset-only extension command is submitted

#### Scenario: Refuse mixed fields
- **WHEN** a client supplies a preset together with pattern, colors, speed, direction or loop
- **THEN** MCP rejects the request before controller dispatch
