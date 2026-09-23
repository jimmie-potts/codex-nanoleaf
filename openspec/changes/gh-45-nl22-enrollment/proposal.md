## Why

[Issue #45](https://github.com/jimmie-potts/codex-nanoleaf/issues/45) asks for a Linux command that adds NL22 Light Panels to an existing Lines installation. [#41](https://github.com/jimmie-potts/codex-nanoleaf/issues/41) added the device registry and [#43](https://github.com/jimmie-potts/codex-nanoleaf/issues/43) runs one worker per registered device, but the only way to register Panels today is to edit the private `config.json` by hand. Nothing verifies the device, starts it safely, or removes it again.

## What Changes

- Add `device-enroll`. It accepts an NL22 address and a credential from a hidden prompt, a private token file, or the device's pairing window (`--pair`). It verifies that the device reports model NL22 and a valid triangle layout, then registers it under a stable id (default `panels`) with its credential under its own configuration key.
- Start a newly enrolled device in Free, with no pending mode change, so its worker sends nothing until the operator runs `mode work --device <id>` or `mode quiet --device <id>`. Enrollment saves the reported geometry, so the worker never needs to rediscover it.
- Make enrollment conservative. All device checks run before any write. The command refuses the reserved `wall` id, an address that another device already uses, and an existing id at a different address. Repeating enrollment for the same id and address replaces only its credential and keeps its layout, mode and reservations.
- Add `device-remove`. It requires the device to be in Free with the handoff applied (`--force` skips that for an unreachable device). It then removes the registration and credential, stops that device's worker, and deletes its layout entry, device-scoped rows and saved scene. Lines and shared tasks are untouched.
- Stop a non-Lines worker instance whose device is no longer registered, instead of retrying forever.
- Explain after enrollment that no service needs a restart. Hooks and the worker read the registry each time they start, and the map, controller and MCP stay Lines-only.
- Update the bridge, development, Linux installation and controller API guides with enrollment, activation and removal.

Unchanged baseline: fresh Linux setup, hooks, task ingestion, allocation, rendering, the per-device worker model from #43, the protected controller and MCP wire contracts and credentials, and the wall map, which still shows Lines only until #44.

## Capabilities

### New Capabilities
- `device-enrollment`: enrollment verification, credential intake, private storage, the Free start, conflict and repeat handling, removal, and operator guidance.

### Modified Capabilities
- `device-worker`: a worker instance for a device that is no longer registered exits instead of retrying.

## Impact

Affected code:

- A new `bridge/enrollment.py` holding the commands, the token reader shared with the installer, and pairing.
- `bridge/bridge.py`: the `device-` command dispatch and the unregistered-device worker exit.
- `bridge/devices.py`: removal of a device's layout entry and state rows.
- `bridge/install_linux.py`: imports the shared token reader.

Tests use temporary Linux state, fake Lines and NL22 transports and the synthetic 18-triangle fixture. No personal device is contacted. The change touches the bridge guide and the development, Linux installation and controller API guides. It does not install anything, change services or hooks, or alter the protected API.
