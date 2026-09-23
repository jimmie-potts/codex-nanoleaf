# 0010. One worker instance per device, and NL22 triangles

Status: Accepted for source implementation in [#43](https://github.com/jimmie-potts/codex-nanoleaf/issues/43).

## Context

After [ADR 0009](0009-device-aware-state.md), every placement, comet, preference, pending edit, Locate, mode and saved scene is stored per device. The Linux installation from [ADR 0007](0007-linux-runtime-ownership.md) still ran one worker loop for the original Lines device (`wall`). That loop also owns work that must stay single:

- polling the shared feed;
- the protected controller's request journal, general controls, overrides and hold;
- the integration settings queue.

The operator wants original NL22 Light Panels to mirror the same tasks with their own mode, scene and failures.

## Decision

The existing worker program runs once per registered device.

- **Locks and launch.** `bridge.py worker --device <id>` takes that device's exclusive lock. The `wall` instance keeps `notification-lock.sqlite`, and other devices use `notification-lock.<id>.sqlite`. Waking the worker launches every registered device, and an instance whose lock is busy exits.
- **Writers.** Each instance sends only to its own address and credential, so each physical device has one writer.
- **Single-owner work.** Only the `wall` instance polls the shared feed and recovers, journals and executes protected-controller and integration-settings work. That includes overrides, the hold and scene discovery. Other instances never create a controller execution.
- **Shared evidence.** Every instance reconciles the shared Codex read evidence and project metadata. Those operations are idempotent, so reading a task clears it on every device even when one device is unreachable.
- **Wake-up and bookkeeping.** An instance wakes on any change to the shared event revision, not on the global `dirty` flag that the other instance may clear first. The applied mode revision, retry error, preview and rendering flag use the `key@device` names from ADR 0009, so `wall` keeps its existing keys.
- **Comets.** A completion queues one comet on each registered device whose mode is Work. Hooks and the shared-input projection read the registry, and an unreadable registry means `wall` only.
- **Clears.** Display-cache clears, refreshes and previews target one device. `setup --reset` and shared-source switching reset the shared task input, so they state that they reset every device. Switching restores bound placements on every device.
- **Retries.** A failed pass records the error for its own device and retries after the existing two seconds.
- **Lock contention.** Worker database connections wait up to five seconds, because another device's pass can hold the write lock for its two 1.2-second requests.

NL22 layouts are read from the device's reported `panelLayout`:

- **Triangles.** `shapeType` 0 is a triangle and becomes one one-zone element. Its id is the panel ID and its position is the reported centroid.
- **Other shapes.** Rhythm and controller modules are excluded. Any other shape is rejected.
- **Validation.** Neighbors are triangles whose centroids lie 150/√3 apart, within 10 percent. Overlap, more than three neighbors, disconnection or invalid values are rejected before anything is saved.
- **Numbering.** Elements are numbered by position after the global orientation, as Lines are.
- **Cache.** Coordinates, per-panel orientation and the neighbor list are kept in `panel_geometry` beside the elements. The reported `sideLength` is not used, because recent firmware reports 0.

NL22 payloads use the same textual `animData` with one zone per triangle and version `2.0`, as in the Light Panels documentation's example. They omit `logicalPanelsEnabled`, which that document does not define and which Lines need for their split zones. Triangles have no project/status halves. Project identity shows through reservations and the map.

## Consequences

Callers that name no device, the protected API wire contract and its fixtures, and a registry without Panels behave as before. Browser controls for Panels belong to #44, and a combined allocation pool to #47.

These protocol points are unconfirmed by the official text:

- the up/down meaning of a triangle's orientation;
- whether a Light Panels controller accepts version `2.0`;
- whether it ignores the missing logical-panel flag.

Source tests use a synthetic 18-triangle fixture and fake transports. [#46](https://github.com/jimmie-potts/codex-nanoleaf/issues/46) owns verifying them on the installed NL22 hardware. An unreachable Panels device retries every two seconds like Lines and records only its own error. Two instances share one database file, and a hook can still wait for one device's send window, as it did before.
