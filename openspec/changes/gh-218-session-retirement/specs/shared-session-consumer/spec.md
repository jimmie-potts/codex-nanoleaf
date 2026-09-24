## MODIFIED Requirements

### Requirement: Validated bounded shared input
The consumer SHALL request snapshot 1.1, require a non-negative safe integer generation no greater than its revision for every session, and validate the versioned snapshot contract and expected owner over authenticated configured numeric-loopback HTTP with bounded time, size and concurrency, no redirects and no proxy use. Source readiness declarations SHALL distinguish operator assertions from verified feed evidence. No provider reducer SHALL be copied to Python. This covers #29 shared-contract, privacy and transport criteria.

#### Scenario: Invalid or unavailable host
- **WHEN** authentication fails, input exceeds bounds, a version/owner/schema is invalid, or a revision regresses
- **THEN** the last valid projection remains with stale/unavailable health and fixed diagnostics, no raw response/credential disclosure and no automatic fallback

#### Scenario: Multiple identities
- **WHEN** concurrent sessions share a project or raw session ID but differ in full source identity
- **THEN** they remain distinct and only explicit bindings connect them to retained local presentation identities
- **AND** Codex sessions may resolve local title and project metadata by provider and raw session ID without merging identities or creating lifecycle state

## ADDED Requirements

### Requirement: Authoritative session retirement
A current owner snapshot that removes a task SHALL remove its task-specific local presentation and release its Lines through the existing allocator. A changed generation for a retained identity SHALL have the same reset effect before projecting the new task. The consumer SHALL preserve unrelated tasks, the global project catalogue, project colors and reservations, preferences, source selection, modes and scenes. Retirement SHALL NOT acknowledge a notice, mark work successful or terminate an agent.

#### Scenario: Removal and empty idle
- **WHEN** the current owner removes a parent and its known descendants, including when the consumer reconnects to an empty snapshot
- **THEN** their tasks and task-specific overrides disappear, their assignments become available, and normal idle behavior applies with no replayed effects

#### Scenario: Missed removal and same-identity recreation
- **WHEN** a later current snapshot has a different generation for a retained identity, including after a consumer restart
- **THEN** the task starts with fresh local defaults and does not reuse its old manual project, assignment or task effects
- **AND** tasks with unchanged generations retain their existing presentation continuity

#### Scenario: Unavailable is not removal
- **WHEN** the feed is unavailable or fails validation
- **THEN** the consumer preserves its last valid projection with unavailable health and does not infer retirement
