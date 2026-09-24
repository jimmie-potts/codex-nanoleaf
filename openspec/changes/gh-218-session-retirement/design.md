## Context

See proposal.md for the missed-removal problem. The existing private saved envelope already survives restart. Snapshot 1.1 changes only the version and per-session generation; all other fields retain the closed 1.0 contract. This design is required for the state migration and cross-repository consumer change.

## Goals / Non-Goals

Keep one shared owner and the existing local transaction/allocator. Distinguish a recreated task without adding a local incarnation counter, polling Codex state, or inferring retirement from revision gaps. Preserve source selection and the sole light writer.

## Decisions

1. Project snapshot 1.1 to 1.0 for the existing checksum-pinned validator, after requiring a safe integer generation on each session. Restore generation on its validated detached mapping. This avoids a copied reducer or schema and an unmerged dependency archive. The Hub harness will exercise the same valid/invalid 1.1 fixture corpus. Live requests require 1.1; old saved 1.0 envelopes are read only as previous state, with imported generation zero.
2. Compare generation by full identity against the last accepted envelope inside the existing SQLite transaction. On change, remove the prior task rows before deriving status or effect timing. Save the new envelope atomically with the projection. A crash therefore retains either complete old or complete new state.
3. Share the task-removal path with authoritative absence. Preserve global project tables and preferences. Clear only retired task metadata, assignments and effects. Recreated rows follow fresh/resync behavior, preventing old completion waves from replaying.

## Risks / Trade-offs

- A 1.0 host cannot supply generation. The new reader reports unavailable until a compatible host is installed; it does not silently fall back.
- A legacy saved envelope cannot identify a retirement already missed before upgrade. The compatible owner imports existing sessions as generation zero; new admissions have a later generation. Continuity requires the same owner/revision lineage.
- Task-specific manual project overrides are intentionally forgotten. Global project definitions and reservations survive.

## Migration Plan

Install a compatible Hub owner first, under separate authorization. Then update the consumer without changing its selected input. Existing private envelopes need no schema migration. Rolling back the consumer loses missed-retirement protection; the old version requires its supported 1.0 endpoint. A Hub durable-format rollback is a separate owner operation and cannot use an older owner against a newer store. Keep the owning Hub issue's installed and visible-device acceptance open until separately qualified.
