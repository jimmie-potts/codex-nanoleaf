## MODIFIED Requirements

### Requirement: Validated bounded shared input
The consumer SHALL validate the released versioned snapshot contract and expected owner over authenticated configured numeric-loopback HTTP with bounded time, size and concurrency, no redirects and no proxy use. Source readiness declarations SHALL distinguish operator assertions from verified feed evidence. No provider reducer SHALL be copied to Python. This covers #29 shared-contract, privacy and transport criteria.

#### Scenario: Invalid or unavailable host
- **WHEN** authentication fails, input exceeds bounds, a version/owner/schema is invalid, or a revision regresses
- **THEN** the last valid projection remains with stale/unavailable health and fixed diagnostics, no raw response/credential disclosure and no automatic fallback

#### Scenario: Multiple identities
- **WHEN** concurrent sessions share a project or raw session ID but differ in full source identity
- **THEN** they remain distinct and only explicit bindings connect them to retained local presentation identities
- **AND** Codex sessions may resolve local title and project metadata by provider and raw session ID without merging identities or creating lifecycle state

