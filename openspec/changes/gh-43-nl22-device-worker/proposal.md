## Why

[Issue #43](https://github.com/jimmie-potts/codex-nanoleaf/issues/43), which absorbed #42's device-worker scope, asks the existing Python worker to show the same task activity on the original Lines and on original NL22 Light Panels. [#41](https://github.com/jimmie-potts/codex-nanoleaf/issues/41) already stores placements, comets, preferences, pending edits, Locate, mode and the saved scene per device. The worker still renders and changes modes for the original device only. Display-cache clears, `setup --reset` and shared-source switching clear every device without saying so.

## What Changes

- Run the existing worker program once per registered device. Each instance has its own exclusive lock and addresses its own device, so each physical device has one writer. Waking the worker wakes every registered device's instance. Without a target, an instance serves the original Lines device (`wall`).
- Mirror task placement. Each device allocates the shared task list independently, using its own reservations, Shared overflow, capacity and waiting list. A full or failing device never moves tasks to the other device.
- Queue completion comets per device, and only on devices in Work. Read and completion evidence remain shared, so reading a task clears it on every device.
- Apply mode, scene restoration, previews, the display cache, the applied-mode revision and the retry error per device. The protected controller ledger, general controls, the integration settings queue, overrides, hold and scene discovery stay with `wall`.
- Isolate failures. A failed pass on one device records that device's error and retries after the existing two-second delay. The other device's instance and outcome are unaffected.
- Add an explicit `--device` target to the CLI `mode`, `status`, `worker` and device-specific `setup` operations. Unknown targets are rejected. `setup --reset` and shared-source switching state that they reset every device, and shared-source switching preserves bound placements on every device.
- Interpret reported NL22 layouts. Triangles (`shapeType` 0) become stable one-zone elements. The Rhythm module and controllers are excluded, and malformed, disconnected or unsupported geometry is rejected. Panel coordinates, orientation and edge neighbors are cached with the layout.
- Render NL22 elements with one zone per triangle and without the Lines-only logical-panel flag. Project signature halves stay a Lines feature.
- Record the per-device worker and NL22 protocol decisions in ADR 0010, and point ADR 0009's gap paragraph at this issue.

Unchanged baseline: task ingestion, the shared-input path, status epochs, pulse, wave, comet and alert rules, the Lines renderer and its paired zones, the protected API wire contract, its fixtures, credentials and replay, and the wall map's Lines presentation. Browser controls for Panels belong to #44, a combined pool to #47, and installation and physical trials to #46.

## Capabilities

### New Capabilities
- `device-worker`: per-device worker instances, mirrored allocation, device-scoped completion queues, per-device modes and scenes, failure isolation, explicit CLI targets, and Lines-only protected APIs.
- `panels-rendering`: NL22 geometry interpretation, triangle payloads, status display, reservations and Locate for one-zone triangle elements, and the synthetic 18-triangle fixture.

### Modified Capabilities
- `linux-runtime`: the one-light-writer requirement becomes one light writer per registered device.

## Impact

Affected code:

- `bridge/bridge.py`: worker, launch, CLI, comets, modes, setup and renderer.
- `bridge/devices.py`: registry helpers and the panel geometry key.
- `bridge/project_map.py`: signatures for one-zone elements.
- `bridge/shared_input.py`: comet targets and switching.
- A new NL22 geometry reader.

Tests use fake Lines and NL22 devices, fake clocks and isolated state, with a synthetic fixture. The change also touches ADRs 0009 and 0010, the bridge guide and the OpenSpec configuration context. It makes no change to installation, hooks, services, the protected API wire format or the browser UI.
