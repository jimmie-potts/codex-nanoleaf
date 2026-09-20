## Context

See proposal.md. The controller provides strict native authentication and a mode ledger. The wall validates edits under SQLite BEGIN IMMEDIATE, merges deferred changes around active comets, and launches the single existing worker. Wall reads are not pure and cannot be reused for machine inspection. #29 provides shared identities without exporting automatic titles.

## Goals / Non-Goals

Expose existing application operations with explicit configuration outcomes. Do not treat saved configuration as physical transmission or add a second light writer, frontend, source-selection control, or shared contract release.

## Decisions

- Use `/controller/integration/v1` and separate request sequence/receipts. Mode control remains `/controller/v1/commands`. The user accepted Nanoleaf ownership; a new shared release would couple this work to another deliverable. Record this in ADR 0008.
- Extract wall validation/application into one transaction-level operation. Both clients use it, while wall reads retain their current behavior. Pure extension reads query allowlisted database fields and validated configured Line pairs, without calling load_config or the wall state handler.
- Use opaque local task/project IDs salted by the controller epoch. Expose qualified shared mappings separately. Never export automatic project names or local task titles. A digest of current configuration and identity/assignment inputs complements the controller revision, detecting metadata or feed changes that do not increment that counter.
- Admit at most one queued configuration edit. Keep it separate from wall pending patches; the worker applies it only when no active comet or wall pending patch remains and its revision still matches. This avoids destructive cancellation of merged wall edits. Expire after 30 seconds. Native/wall edits cause a conflict instead of silent last-writer-wins.
- Application and receipt commit atomically. Receipt `applied` means configuration saved; `physicalOutcome: unknown` remains explicit. Configuration work does not reset transport retry holds or replay mode commands. Cancellation/revocation/disable removes only uncommitted work; it never rolls back a committed edit or borrows browser credentials.
- Keep 256 receipts, bounded read collections and the existing HTTP limits. Reads can return capacity rather than truncate identity maps into a misleading editable subset. Reconnect uses snapshots/receipts and never submits requests automatically.

## Risks / Trade-offs

- Task/project catalogs can change between admission and execution. Revision checks fail closed; consumers refresh and request a new edit explicitly.
- Configuration success is not optical evidence. Outcomes keep physical evidence unknown; current v1 mode transport evidence remains separate.
- A held worker or long comet can delay work. Expiry, explicit cancellation and launch failure provide bounded outcomes without automatic write retries.
- Additional tables must not break rollback. Older source ignores them; cancel pending requests and stop the listener before downgrading, retain the current database.

## Migration Plan

Initialize extension tables in ordinary source-managed state initialization without enabling services. Package the new module with both existing installer paths. Test isolated native Linux and retained Windows source paths; personal installation is excluded. Publish docs/fixtures alongside the source and reconcile the linked Hub guide companion.
