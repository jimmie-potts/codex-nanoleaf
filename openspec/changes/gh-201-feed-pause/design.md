## Context

See proposal.md for the consumer boundary required by Hub #557. The shared core already reseeds in stop → seed → launch → readiness order and clears data/home/tmp while preserving runtime-root token files. Holding pause through readiness would prevent the fresh consumer from accepting the reset owner.

## Goals / Non-Goals

Keep the live consumer responsive while the owner resets, with a verifiable drain boundary and a safe handoff to fresh consumer state. This is a disposable verification control; installed configuration, shared core versions and public APIs are unchanged. A general coordination service or cross-process lock for arbitrary independent per-run commands is outside scope.

## Decisions

The existing paired writer holds one lock across the real Poller and local worker updates. Check the pause before the next poll, acknowledge under that lock after any previous poll drains, and continue local allocation and controller work. The demo receives explicit paired-only run identity and runtime directory arguments.

Use the existing private runtime directory. `feed-pause.request` and `feed-pause.release` contain strict JSON `{version:1,runId,nonce}`, with a 32-character lowercase hexadecimal nonce. `feed-pause.ack` adds the live process's positive integer `pid`. Reads are bounded to 4 KiB, regular, owned, private files without symlinks. Acknowledgments use mode 0600 and atomic replacement; no credential appears in controls or errors.

A pause stays active through the owner reset. Hub validates its nonce and the receipt's systemd process identity, then writes release authorization only after its owner reseed succeeds. Consumer seed checks authorization before writing and consumes it after successful seed, before fresh launch. An unconditional seed-time unlink could resume an old consumer during owner reset; leaving pause through readiness would prevent recovery. Neither alternative satisfies the contract.

Diagnostics skip with an explicit pause reason and do not probe Hub while paused; invalid controls fail. Hub must require ordinary passed checks after release. The acknowledgment covers this serving process's requests. The coordinator serializes aggregate mutations and avoids concurrent per-run doctor/capture/scenario operations while resetting.

## Risks / Trade-offs

- A paused feed might appear current → retain the prior snapshot but preserve existing age/freshness semantics and mark observation stale where required.
- A request changes during acknowledgment or seed → recheck run and nonce before publishing or consuming controls; never remove a newer request using old authorization.
- Reset fails halfway → retain the pause and report the named error; existing core stop remains the cleanup path. No automatic rollback or command retry is introduced.
- Private runtime files are removed or made invalid → stop admission and withhold successful acknowledgment instead of silently ignoring the request.

## Migration Plan

Land this opt-in source change with independent review and CI. Hub #557 updates its composition pin only after this delivery passes its own gates. No installation or live-state migration occurs. A failed disposable run can be stopped and started again with the existing commands; frozen local proof remains separate.
