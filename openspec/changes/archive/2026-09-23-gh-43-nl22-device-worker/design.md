## Context

See proposal.md. After #41, every device-scoped table carries a `device` column. The layout file holds one entry per device, and `load_config(directory, device)` resolves one device's address, credential and elements. `run_worker` is still one loop for `wall`:

- It takes `notification-lock.sqlite`.
- It polls the shared feed.
- It reconciles Codex unread evidence.
- It processes integration-settings requests and protected-controller controls under the controller ledger.
- It renders through `SceneRestorer` while holding the database write lock during device sends.

Hooks and the map wake it through `launch_worker(directory)`.

## Goals / Non-Goals

**Goals:**

- Give each registered device its own writer and its own mode, scene, comet queue and failure state.
- Keep one ingestion path and the shared task records.
- Add NL22 triangles as a second element shape.
- Leave callers without a target and the protected APIs on `wall`.

**Non-Goals:**

- Panels over the controller, integration or MCP APIs.
- A browser UI for Panels (#44).
- A combined pool (#47).
- A "both devices" CLI operation.
- Windows.
- Streaming output.
- Physical acceptance (#46).

## Decisions

### Worker instances

- **One worker instance per device.** `bridge.py worker --device <id>` runs the existing `run_worker` for one device.
  - `wall` keeps `notification-lock.sqlite`, so an older running worker still excludes a new one. Other devices use `notification-lock.<id>.sqlite`.
  - `launch_worker(directory)` starts one process per registered device. An instance whose lock is busy exits immediately, as today.
  - Rejected alternative: one process interleaving devices. A blocking preview or a device timeout on one device would delay the other, and failure isolation would need a second scheduler. Separate instances reuse the existing lock, retry loop, previews and deadlines unchanged.
- **Ingestion stays single.**
  - Only the `wall` instance polls the shared feed. It also recovers and processes protected-controller requests, general controls, the integration settings queue, scene discovery for the controller snapshot, overrides and the hold.
  - Every instance reconciles Codex unread evidence and project metadata. Both operations are idempotent updates of shared rows under the existing transaction, so read clearing does not depend on `wall`'s device being reachable.
  - A non-`wall` instance never builds a controller `Execution`, so its sends cannot journal into, cancel or overwrite a controller receipt, last successful send or last outcome.
- **Wake-up and bookkeeping.**
  - `dirty` stays the global signal that a hook or map uses to decide whether to launch.
  - An instance leaves its wait loop when `event_revision` differs from the revision its pass rendered, or when a preview for its device appears. One instance clearing `dirty` therefore cannot hide a change from the other.
  - `rendering`, `preview`, `mode_applied` and `control_error` use the existing `devices.meta_key` naming, so `wall` keeps its current keys.
  - A device's retry error is written only under its own key.
- **Lock contention.** Device sends stay inside the pass's write transaction, as today. Worker connections use a five-second busy timeout, and hooks keep 2.5 seconds. One device's pass holds the lock for at most two 1.2-second requests, so the other instance waits instead of failing.
- **Retries.** A failed pass keeps the existing bounded retry: the device's error is recorded and the pass retries after two seconds. As for Lines today, the retry repeats until a pass succeeds. The delay is bounded; the number of attempts is not. Each instance retries only its own device.

### Tasks, modes and effects

- **Comets per device.** A completion inserts one queued comet for each registered device whose mode is Work. Hooks read the registry from the private configuration, and the shared-input projection receives the same targets. Any read failure falls back to `wall`. A device registered later starts with an empty queue, so it replays nothing.
- **Mirrored allocation.** `dashboard` and `wall.allocate` already filter by the configuration's device. Each instance allocates the same shared task rows against its own elements and preferences, and the waiting list is derived per device. Activity epochs are shared, so both devices show the same pulse phase.
- **Scoped clears.**
  - Worker cache invalidations and `setup --refresh` clear only their device's display cache. So do previews (`--demo`, `--notify`, `--comet`) and `--check`.
  - `setup --reset` clears shared tasks. It is therefore a reset of every device, and its message says so.
  - Shared-source switching already replaces the shared task input for every device. It keeps that scope explicitly, and it restores bound placements on every device instead of only `wall`.
- **CLI targets.** A global `--device` option is validated against the registry, and an unknown id exits with an error. Omitting it addresses `wall` whatever the registry order.

### NL22 geometry and payloads

- **Geometry.** `panels.read_layout(panel_layout)` validates the documented Light Panels layout:
  - Accepted fields are `positionData` entries with `panelId`, `x`, `y`, `o` and `shapeType`, plus `globalOrientation`.
  - `shapeType` 0 is a triangle. Types 1 (Rhythm), 3, 4 and 12 (controllers) are excluded non-light modules. Every other type is rejected.
  - Panel ids must be integers from 0 to 65535 and unique. Coordinates and orientation must be finite.
  - Neighbors are triangles whose centroids lie one inradius pair apart (side 150 / √3 ≈ 86.6, ±10%). Closer centroids are rejected as overlapping, more than three neighbors are rejected, and the triangles must form one connected arrangement.
  - Elements are numbered by position after applying the global orientation, as Lines are. A triangle's id is its panel id, and its position is its reported centroid.
  - The cached `panel_geometry` keeps each triangle's id, coordinates and orientation, the global orientation and the neighbor list.
  - `sideLength` is not trusted, because firmware 5 reports 0.
- **Discovery ownership.** `load_config` discovers an NL22 layout only when no valid saved entry exists, as it does for Lines. It then saves the entry atomically. The map, snapshot and feed readers never call it for Panels.
- **Payload.** Lines keep `version: 2.0` and `logicalPanelsEnabled: true`. NL22 payloads use the same textual `animData`, with one zone per element and `version: 2.0` as in the Light Panels example, and they omit `logicalPanelsEnabled`, which the Light Panels document does not define.
  - Project signatures apply only to two-zone elements. A triangle always shows its status.
  - The official document does not confirm up/down orientation semantics or whether `logicalPanelsEnabled` is accepted. #46's physical trial owns verifying the payload on hardware.

## Risks / Trade-offs

- **Two processes contend for one SQLite file.** Both instances use the existing short transactions. The longer worker busy timeout absorbs the other device's send window. Hooks keep their timeout: their exposure was already one device's send window and remains one window at a time.
- **An unreachable Panels device retries every two seconds.** This matches the existing Lines retry and is confined to that device's instance and error key.
- **Guessing NL22 protocol details.** The renderer follows the official Light Panels document where it is explicit. Unknown details are isolated in the Panels renderer branch and flagged for #46.
- **Rollback.** #41's source ignores the extra lock file and meta keys and never starts a Panels instance. Its normalizer still accepts the Panels layout entry and drops only the unknown `panel_geometry` key when it rewrites the file.

## Migration Plan

Nothing migrates. The first launch after upgrade starts one instance per registered device. A configuration without Panels behaves exactly as before, with one `wall` instance and the same lock and meta keys.
