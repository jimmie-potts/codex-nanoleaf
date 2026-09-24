## Context

The worker generates the Nanoleaf `animData` payload in `bridge/bridge.py`. `update_display` runs the controller sender and only then commits a per-device `display_v3` record in the existing `status.sqlite`. The wall server's `/api/state` calls `App.state`, which refreshes metadata and may acquire device geometry; it is not a passive rendering read. Dynamic effects send `/effects` and brightness in separate controller requests. The current browser animation is intentionally indicative; #17 owns rendering this snapshot.

## Goals / Non-Goals

**Goals:**
- Return the latest fully successful worker output, its physical zone mapping, and timing through a passive endpoint on the existing local map server.
- Report pending, failed, unknown, and Free/external output without presenting an unsuccessful send as accepted.
- Persist only the latest receipt in the existing private state database.

**Non-Goals:**
- Change browser animation, add a second scheduler or writer, or verify optical output.
- Add output history, event streaming, subscriptions, a new listener, or generalized client authentication.
- Add Windows-specific output support or change existing installation behavior.
- Capture arbitrary Nanoleaf scenes whose frames the worker cannot read.

## Decisions

1. **Add `GET /api/rendering` to the existing loopback server.** Read directly from a read-only SQLite connection and retain Host and no-store protections. Do not extend `/api/state`: its metadata and geometry refresh can cause unrelated state changes, device reads, or worker launches. A route on the existing listener adds no new service or authentication system, and #17 can poll it when implementing the renderer.

2. **Keep one latest receipt in the existing `meta` key/value table.** Store it under a device-scoped key only after the complete dynamic worker send succeeds. This avoids a schema/table migration and preserves it across worker and map-server restarts. An older database without a receipt simply reports `unknown` until the next successful worker render; no task or preference data is rewritten.

3. **Persist the exact encoded effect command and its zone mapping.** Include the existing `write` payload, per-Line zone IDs, mode, effective brightness, loop flag, animation epoch, request start, and successful completion time. These timestamps describe the local schedule and successful HTTP exchange; none claims when photons appeared. The loopback response adds a sample time in the same wall-clock domain.

4. **Record only completed worker output.** `render` returns receipt data after both `/effects` and brightness requests succeed; `update_display` commits it with its existing per-device display record. If a request fails, the previous receipt remains the last fully successful output and the existing worker error/pending state reports the incomplete attempt. Do not store a partially accepted attempt as successful.

5. **Derive outcome from existing state.** Free mode reports externally controlled output. Queued dirty or mode work reports pending; a worker error reports failed/uncertain; a missing receipt reports unknown; otherwise return last-sent. Include the last successful receipt separately when pending or failed. The endpoint uses a SQLite read-only URI and never calls metadata, geometry, or controller helpers.

## Risks / Trade-offs

- [Controller accepted output may differ from visible output] → State that the receipt proves successful command acceptance only; physical comparison remains #17's acceptance work.
- [A failed pass can have applied some earlier requests] → Keep its status failed/uncertain and retain only the prior fully successful receipt; never label the partial pass as the current successful receipt.
- [An external saved scene may be active without readable frames] → Return unknown/external state and no fabricated timeline.
- [Existing installations have no receipt at upgrade] → Return unknown until a normal successful worker render writes the latest receipt; use the existing SQLite initialization path without resetting user data.

## Migration Plan

No schema migration is required. New code writes one device-scoped key in the existing `meta` table after a successful worker render. Existing state without that key remains valid and reads as unknown. Rollback removes the additive response field and ignores the unused key; task, scene, and map state are unchanged.
