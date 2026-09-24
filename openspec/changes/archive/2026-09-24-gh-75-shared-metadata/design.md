## Context

See proposal.md for motivation. Shared projection rewrites task_info each poll; project membership controls allocation. Metadata.sync currently scans legacy session keys and is disabled in shared mode. This change crosses the reader, projection, worker and wall API, so a design is required.

## Goals / Non-Goals

Goals: reuse lookup rules, refresh metadata before shared projection, preserve lifecycle and effects.
Non-goals: provider reducers, Claude metadata, schema changes, shared uploads, installation or new writers.

## Decisions

- Extract catalog synchronization and single-session lookup from Metadata.sync. Legacy sync uses the same helpers; shared projection calls lookup only for Codex raw identities. Running legacy sync over shared hashed keys would lose identity and risk changing precedence.
- Give the worker's Poller a cached Metadata reader. Refresh outside the write transaction; initial selection and direct acceptance construct a reader from the local config file when none is supplied. Never use device-aware load_config to perform a metadata lookup.
- Persist resolved title and project in task_info within the same transaction as shared projection. Compare presentation values and catalog changes to mark rendering dirty even at an unchanged owner revision. Do not update session timestamps or activity epochs for metadata-only changes.
- Use one provider-aware fallback helper. Store shared fallback titles during projection; wall API uses the helper for legacy blank titles. Render the existing UI without layout changes.

## Risks / Trade-offs

- Missing or malformed files: the existing reader retains valid cached metadata and falls back safely; no lifecycle is inferred.
- Private metadata leakage: enrich only local SQLite; leave shared requests and sanitized inspection unchanged.
- Concurrent source changes: projection remains under the existing generation check and transaction.
- Stale local task indexes: lookup never enumerates new sessions, so owner retirement remains authoritative.

## Migration Plan

No schema migration. Source delivery requires Python, browser and workflow checks, independent reviews and human UI approval. Installation belongs to #89; retain legacy selection until its cutover checks pass. Source rollback restores the prior reader/projection without changing hooks or modes.
