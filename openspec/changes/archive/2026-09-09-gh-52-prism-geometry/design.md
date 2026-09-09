## Context

See the proposal and issue #52. The current zone cache filters out non-light entries, and its presence prevents enrichment. The fixture contains connector types 16, 19, and 20, with two controller entries at one housing. Its visible Line endpoint estimates stop slightly short of reported connector centers.

## Goals / Non-Goals

Provide a validated graph in the same coordinate frame as existing Line points. Keep the old projection usable, and avoid touching the database or worker in geometry acquisition. Do not introduce a device registry or change installation ownership.

## Decisions

- Keep a separate additive `connector_geometry` cache of whitelisted raw positions and controller orientation. Existing zone-only geometry and old callers remain unchanged. Prefer already cached complete data before requesting the controller.
- Build `connector_layout` from validated cache data through a pure geometry helper. Node IDs derive from sorted source IDs; Line IDs and numbering derive from existing group order. Apply controller orientation and inverted display Y in the producer. The browser alone applies its map rotation and flips.
- Resolve each end against reported connector centers within a bounded fraction of zone spacing, requiring a unique candidate, aligned centerline, and compatible six-face angles. Reject incomplete mappings rather than accepting the nearest arbitrary housing. Merge only co-located supported housing entries within rounding tolerance. Reject duplicate zone IDs, non-finite data, unknown shapes, duplicate occupied faces, and oversized input.
- Publish the validated additive cache with the bridge's existing atomic JSON writer before updating memory. The App lock serializes acquisition and state reads. Use a map-owned `connector-geometry.json` sidecar; never read-modify-replace shared `layout.json`. Read valid legacy embedded caches for compatibility and hydrate missing zone points from the sidecar on restart. A failed write leaves memory and disk unchanged.
- Make at most three automatic acquisition attempts per server lifetime, spaced by ten seconds. Valid complete caches require zero requests. Startup is the first attempt; subsequent state reads schedule remaining attempts. This permits recovery from a transient failure without a permanent poll loop in Free mode. Restarting the wall server permits another bounded acquisition window.

## Risks / Trade-offs

- Controller rounding can make exact collinearity impossible. Test the real sanitized fixture and allow one degree of angular rounding; large or ambiguous deviations fail closed to the old wall.
- A legacy cache may remain the only available geometry while the controller is offline. Continue drawing the old wall and expose a sanitized availability field rather than clearing it.
- Layout configuration has other owners. Keep its writes separate from the map-owned sidecar; the existing map-server singleton and App lock own connector enrichment. The sidecar envelope binds validated geometry to the layout file generation (mtime, size and file identity), so the existing remove-layout/rediscover procedure cannot reuse stale connectors when IDs remain unchanged. State reads compare the live file generation even when an in-memory graph exists. A changed file uses the same bounded acquisition budget and delay; successful refreshes replace connector and legacy zone drawing points together, while failures retain the prior graph. This private metadata is not projected to the browser. No worker state is rewritten.

## Migration Plan

This source change enriches only the geometry cache during normal wall initialization. It requires no installation migration, task reset, or fresh setup. Old source ignores the additive cache. A failed acquisition or write keeps the prior cache. Linux service setup remains separately owned.
