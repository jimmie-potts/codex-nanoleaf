## Context

See proposal.md for the missed-removal problem. The existing private saved envelope already survives restart. Snapshot 1.1 changes only the version and per-session generation; all other fields retain the closed 1.0 contract. This design is required for the state migration and cross-repository consumer change.

## Goals / Non-Goals

Keep one shared owner and the existing local transaction/allocator. Distinguish a recreated task without adding a local incarnation counter, polling Codex state, or inferring retirement from revision gaps. Preserve source selection and the sole light writer.

## Decisions

1. Project snapshot 1.1 to 1.0 for the existing checksum-pinned validator, after requiring a safe integer generation on each session. Restore generation on its validated detached mapping. This avoids a copied reducer or schema and an unmerged dependency archive. The Hub harness will exercise the same valid/invalid 1.1 fixture corpus. Live requests require 1.1; old saved 1.0 envelopes are read only as previous state, with imported generation zero.
2. Compare generation by full identity against the last accepted envelope inside the existing SQLite transaction. On change, remove the prior task rows before deriving status or effect timing. Save the new envelope atomically with the projection. A crash therefore retains either complete old or complete new state.
3. Share the task-removal path with authoritative absence. Preserve global project tables and preferences. Clear only retired task metadata, assignments and effects. Recreated rows follow fresh/resync behavior, preventing old completion waves from replaying.
4. In shared mode include idle root tasks in allocation and the wall list. Render idle as steady blue without a new wave or comet. Keep the orphan-child rule and legacy projection unchanged. This retains presentation without inventing a lifecycle event or local expiry timer.
5. Store eviction in a local table keyed by device and presentation identity, with a fingerprint of owner, source selection, generation and turn identity. Filter that device's allocation and wall rows while it matches. Remove its task slots and queued/running task comets in the same transaction; other devices and tasks retain their presentation. Read/acknowledgment, reconnect and process restart do not clear eviction. A changed identifiable turn or generation clears the marker, while authoritative absence removes it with other task state.
6. Expose an opaque eviction fingerprint with shared wall tasks. The existing same-origin edit-token protected POST requires that fingerprint to match the saved owner projection before changing local state. A stale button cannot evict a recreated task or newer turn. Repeating a matching eviction is harmless. No new shared-owner credentials or device transport path is needed. Global eviction would require an explicit owner command and is deferred.

## Risks / Trade-offs

- A 1.0 host cannot supply generation. The new reader reports unavailable until a compatible host is installed; it does not silently fall back.
- A legacy saved envelope cannot identify a retirement already missed before upgrade. The compatible owner imports existing sessions as generation zero; new admissions have a later generation. Continuity requires the same owner/revision lineage.
- Task-specific manual project overrides are intentionally forgotten. Global project definitions and reservations survive.
- Eviction is local presentation suppression, not shared retirement. It does not empty the owner for future mode automation. The UI states this scope.
- With unknown turn identity, the consumer cannot reliably distinguish new work within one generation. It retains eviction until an identifiable new turn or new generation rather than guessing from elapsed time or read state.

## Migration Plan

Install a compatible Hub owner first, under separate authorization. Then update the consumer without changing its selected input. Existing private envelopes need no migration; a new empty eviction table is created by the normal local-state initialization. Older consumer code ignores that table and can show evicted tasks again. Rolling back the consumer loses missed-retirement protection; the old version requires its supported 1.0 endpoint. A Hub durable-format rollback is a separate owner operation and cannot use an older owner against a newer store. Keep the owning Hub issue's installed and visible-device acceptance open until separately qualified.
