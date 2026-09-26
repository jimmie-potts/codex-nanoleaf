## Context

The worker saves scene-state.json and advertises HMAC scene IDs in its private controller ledger. Animation discovery uses a separate route from the exact extension snapshot.

## Goals / Non-Goals

Expose the existing restore target and invoke one existing scene activation. Brightness writes, automatic restoration, mode switching and Panels restoration remain outside this change.

## Decisions

Read the existing scene file without constructing a worker or observing the device. Match its saved name against the ledger's advertised scene names, returning that existing opaque ID or null. Missing or unreadable saved state returns null without a write.

The tool accepts the shared v1 identity fields from nanoleaf_status, reads animation options, then delegates to the same handler as nanoleaf_scene_activate. Recheck credentials at the existing dispatch boundary. Work/Quiet and absent targets fail typed before dispatch; a concurrent mode or scene change remains subject to controller admission and worker validation. Preserve receipts and uncertainty without retries.

## Risks / Trade-offs

- The scene file and ledger are separate snapshots: existing controller and worker scene validation remain authoritative at dispatch.
- A read-only credential cannot perform restoration: the tool remains control-scoped and upstream reads enforce their existing authorization.
- Saved brightness is not sent: the existing policy and issue explicitly defer a new brightness command.
