## Why

[Issue #41](https://github.com/jimmie-potts/codex-nanoleaf/issues/41) needs the Linux bridge state to describe more than one Nanoleaf device before [#42](https://github.com/jimmie-potts/codex-nanoleaf/issues/42) integrates a second renderer and [#43](https://github.com/jimmie-potts/codex-nanoleaf/issues/43) adds NL22 geometry. Today every placement, reservation, pending edit, comet, mode and saved scene is implicitly the single Lines device, and the layout file is a Lines-only zone pairing.

## What Changes

- Add a small device registry in the private configuration: id, kind (`lines` or `panels`), address and a token reference. The original Lines device keeps the controller identity from #28 (`wall`); callers that name no device continue to address it.
- Give device-scoped state a device key: slot assignments, comets, Line preferences, display cache, map settings, pending map edits, Locate, mode metadata and the saved scene file. Uniqueness becomes device plus slot and device plus element, so one task can hold one placement per device and equal panel IDs on two devices cannot collide.
- Migrate an existing Linux database in place inside the existing initialization: guarded, idempotent, defaulting every existing row to the original Lines device, and preserving tasks, epochs, preferences, pending edits, the active comet and controller history.
- Replace the Lines-only layout pairing with one entry per device whose elements carry a physical ID, the existing number and a zone list (two zones for a Line, one for a triangle). Legacy layout files remain readable; a malformed layout is rejected without replacing the last valid one.
- Record the decisions in ADR 0009 and link the new capability from the guides.

Unchanged baseline behavior: task ingestion, task IDs, project identity, task-project overrides, status epochs, tool waits and Codex unread evidence keep one shared owner. The existing worker stays the only light writer and still renders the original Lines device. Windows installations, adapter layers, a pool identity, NL22 layout reading and Panels rendering are out of scope.

## Capabilities

### New Capabilities
- `device-state`: device registry, device-qualified element identity, device-scoped state and layout shape, and the Linux-only in-place migration.

### Modified Capabilities

None. The Linux runtime, protected controller, integration settings, wall identification and presentation specs keep their requirements; they gain the default device through the new capability.

## Impact

`bridge/bridge.py` initialization, mode and comet helpers; `bridge/project_map.py` preferences, settings, pending edits and geometry; `bridge/wall_server.py`, `bridge/integration_api.py`, `bridge/shared_input.py` and `bridge/install_linux.py` readers of the layout and device-scoped tables; a new `bridge/devices.py`; isolated tests with a committed pre-change Linux fixture; ADR 0009 and guide links. No installation, hook, service, UI or physical change.
