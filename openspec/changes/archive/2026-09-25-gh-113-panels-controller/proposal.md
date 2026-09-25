## Why

[Issue #113](https://github.com/jimmie-potts/codex-nanoleaf/issues/113) makes the NL22 Light Panels a second device of the protected controller, so the hub, the dashboard and Codex can control them the same way as the Lines. Today the controller has one identity and one ledger. [ADR 0010](../../../docs/decisions/0010-per-device-worker-and-nl22.md) assigns all controller work to the `wall` worker: the request journal, general controls, overrides, the hold and scene discovery. The Panels can be controlled only from the CLI.

The owner settled the design at the delivery checkpoint (issue comment of 2026-09-25):

- Each controller device gets its own ledger, and that device's worker owns the ledger. [ADR 0015](../../../docs/decisions/0015-per-device-controller-ledgers.md) records the decision.
- A credential covers every configured device.
- The integration extension is read-only for the Panels.

## What Changes

- **Per-device ledgers.** The controller keeps one ledger per configured device. Each ledger has its own identity and epoch, configuration revision, generation, request journal and sequence, event feed, scene key and discovered scenes, last send and last outcome. The `wall` ledger keeps its existing rows. Its overrides and hold keep their meta keys, so its epoch, receipts, cursors and scene IDs survive. Other devices use the ADR 0009 `key@device` meta names.
- **Adding a device.** `controller-configure` with the same controller and source IDs and the ID of a registered device other than `wall` adds that device's ledger. Redirecting an existing identity is still rejected. So is naming an unregistered device.
- **Routes.**
  - `/controller/v1/devices` lists every configured device, Lines first.
  - Snapshot, feed and command routes select the ledger named by `deviceId`. An unknown device is still `unknown-device`.
  - One credential authorizes every configured device.
- **Per-device worker ownership.**
  - Each worker instance recovers, holds, journals and executes its own device's v1 requests (mode, power, brightness, `scene.activate`) and records its own scene discovery.
  - The `wall` instance alone still polls the shared feed and applies the integration settings queue and requested animations.
  - A mode change for one device supersedes only that device's queued controls.
- **Integration extension.** For a non-Lines device, the extension snapshot shows that device's identity, revision, mode and scenes, and it marks the configuration operations unsupported. Extension commands, including `animation.play`, fail with `unsupported-capability` before reservation. Receipt and cancel lookups under that device return `request-expired`, and the animations route returns `unsupported-capability`.
- **MCP.** An optional `panelsDeviceId` in the MCP configuration binds a second fixed target with `nanoleaf_panels_status`, `nanoleaf_panels_mode_set`, `nanoleaf_panels_scenes_list` and `nanoleaf_panels_scene_activate`. Callers still cannot choose a device.
- **Display version 2.0.** The #46 physical acceptance showed the Panels accept `display` version `2.0` custom effects without `logicalPanelsEnabled`. ADR 0015 records that answer for #92.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `protected-controller-api`: per-device ledgers, the multi-device devices route and migration of the existing ledger.
- `device-worker`: each instance owns its own device's controller work. This replaces "Protected APIs stay on Lines".
- `integration-settings-api`: a read-only extension view for devices other than the Lines.
- `local-mcp-bindings`: an optional fixed Panels target.

## Impact

- **Code:** `bridge/controller_state.py`, `bridge/controller_server.py`, `bridge/integration_api.py`, `bridge/bridge.py` (mode notification and worker ownership) and `mcp/src` (config, tools, transport, server).
- **Tests:** the Python controller, worker and integration suites and the MCP tests.
- **Docs:** `docs/controller-api.md`, `docs/local-mcp.md`, `docs/integration-api.md`, `bridge/README.md`, ADR 0010 (status note) and ADR 0015.
- **State migration:** `controller_meta`, `controller_requests` and `controller_events` gain a `device` column (the last two are rebuilt with a per-device key). `integration_requests` is unchanged, because extension commands stay Lines-only. After the upgrade, older source can still read the Lines ledger, but its admission insert fails closed.
- **Out of scope:**
  - Installing, provisioning a Panels ledger on the live installation, the hub controller entry and physical checks. The owner requests these separately.
  - Animations on the Panels (#92 follow-up) and a project glossary (#163).
- **Known gap:** the hub's closed `validateIntegrationSnapshot` requires every configuration operation to be `supported: true`, so the hub rejects the Panels' read-only extension snapshot until the hub accepts unsupported operations. Hub v1 control of the Panels (snapshot, power, brightness, mode, scenes) and MCP scene listing don't use that validator.
