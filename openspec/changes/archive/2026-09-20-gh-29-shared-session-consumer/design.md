## Context

See proposal.md. The current hook reduces local Codex events into SQLite; an on-demand worker renders that projection. Pixoo's delivered `/api/monitor/v1/sessions` wraps the released Agent State 1.0 snapshot. Notifications are pointers, not a replayable effect log. The selected Nanoleaf runtime remains OS-local.

## Goals / Non-Goals

Support a persisted installation-wide source selection and one Python worker. Preserve legacy behavior and expose pure sanitized inspection for later settings APIs. Do not implement producer qualification, shared hook installation, standalone hosting, new dashboard UI, additional devices, or shared provider interpretation.

## Decisions

- Pin the immutable Agent State 1.0.0 archive and extract its unchanged Python validator, schema and fixture corpus. Legacy mode does not import jsonschema. Validate snapshots before projection and reject closed-schema violations, identity duplication and revision regression.
- Poll the configured numeric IPv4 loopback endpoint once per second from the existing worker with one in-flight request, a bounded response and a total transport deadline. Keep network I/O outside SQLite transactions. The persistent shared worker observes source generation changes before applying responses. Bounded polling avoids another service and SSE transport implementation; reconnect applies current state without replay.
- Keep source selection, configuration, health and presentation records in private SQLite. Source configuration contains a private token-file reference, never a public credential. No feed request contains local titles, roots or paths. Only explicit shared labels/project IDs enter the new projection. Provide `shared-configure`, `shared-preflight`, `shared-select`, `shared-status`, and `shared-acknowledge` source commands. Pure inspection does not migrate/write state or contact the host.
- Preflight requires compatible current owner, authenticated feed, configured qualified source declarations and operator-confirmed host consumer policy `clearOnNewTurn: true`. The host's read API does not expose producer qualification or consumer configuration; declarations are explicit installation evidence, not discovered or falsely claimed qualifications. Hub #8 owns their provisioning. Selection validates first, then commits atomically; only the selected input updates task state. Owned legacy hook handling becomes a no-op in shared mode; unrelated hooks are never edited.
- Preserve a private legacy projection at cutover, with explicit full-identity-to-local-session bindings for continuity. Do not guess that identical IDs across hosts/providers are the same task. Transfer bound assignments, local project association and epochs without uploading them. Rollback restores the legacy projection and carries current bound presentation preferences/assignments back, suppressing old waves/comets. Leave scene/mode/project/Line preferences untouched. Reject cutover during an active comet reservation rather than stealing its source.
- Shared attention maps approval/input to blocked, continuing question to question, active to working, an unacknowledged notice to unread, and other states to idle. Known read evidence suppresses the local blue indicator only. Acknowledgment targets the exact notice and configured consumer with a current request identity; no invented read receipts or successful-work claims. Clear-on-new-turn is performed by the shared owner, not a Python reducer.
- User decisions: uncertain/disconnected sessions retain last colors steadily; healthy peers retain their behavior. Suppress stale waves/comets and keep effect epochs; a current snapshot resumes local pulses without a new outward wave. Expired/intermediate completion effects are never replayed on initial load, restart, loss, revision gaps or reconnect. Free continues tracking without task-light writes.
- Expose selected source, neutral owner, connection, revision, evidence age, unknown read capability and fixed error codes through pure CLI/module inspection. Keep tokens, token paths and local metadata out of diagnostics. The future integration-settings API consumes this projection; no UI candidate is introduced here.

## Risks / Trade-offs

- Polling can miss intermediate statuses: reconcile current status and suppress uncertain effect replay; report revision gaps and loss.
- The host's consumer policy/qualification is not queryable: require explicit setup assertions, document limits, and verify installed operation in #30/Hub #8.
- Shared status adds host dependence: retain stale presentation and explicit rollback, never automatic legacy fallback.
- Cross-host clocks: use supplied observation age plus local monotonic elapsed time for freshness and local presentation epochs; do not compare unrelated clocks for effect timing.
- Legacy rollback cannot recover events intentionally not ingested during shared mode: restore retained state as stale until new local evidence, preserve preferences, and document this boundary.

## Migration Plan

Source delivery adds modules, private schema and commands, but activates nothing. During separately authorized installation, configure the host's Nanoleaf consumer with clearOnNewTurn enabled, qualify producers, provision a read credential and optional acknowledgment control credential, declare bindings, run preflight and select shared. Keep the same device writer. Roll back explicitly to legacy; shared data remains private and inactive. Never run fresh setup to perform this cutover.
