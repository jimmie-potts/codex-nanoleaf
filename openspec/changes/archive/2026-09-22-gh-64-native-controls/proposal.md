## Why

[Issue #64](https://github.com/jimmie-potts/codex-nanoleaf/issues/64) needs the protected controller to advertise and execute power, brightness and saved-scene activation so the shared BUNNY frontend ([hub #153](https://github.com/jimmie-potts/agent-device-hub/issues/153)) can offer Nanoleaf general controls without an agent session. The accepted definition is hub ADR 0005 under [hub #31](https://github.com/jimmie-potts/agent-device-hub/issues/31). Released controller v1 already carries `power.set`, `brightness.set` and `scene.activate`, so no shared contract release is required.

## What Changes

- Declare `power`, `brightness` (0 to 100) and `scenes` (discovered IDs, at most 256) as supported v1 capabilities; `media`, `zones` and `preview` stay unsupported. The vendored contract archive, schema and 220 fixture cases are unchanged.
- Discover saved scene identities from the worker's existing scene observation and advertise them as opaque IDs keyed by a private ledger secret. Expose the user-chosen Nanoleaf scene names only through the `nanoleaf.integration/1.0` snapshot, as an additive `scenes` field within the shared label bound.
- Execute `power.set`, `brightness.set` and `scene.activate` as one-shot writes through the existing single worker queue with the #28 replay, revision, generation, uncertain-hold and single-writer rules. Mode commands keep their current path.
- Define the override policy: power and brightness are accepted in Work, Quiet and Free, become the desired state at acceptance, govern the worker's later writes in the current mode, and are cleared by the next explicit mode command (tray, CLI, wall or native, including the same mode), which reapplies that mode's brightness and power policy.
- Accept `scene.activate` only when the desired mode is Free; in Work or Quiet it returns the existing typed `unsupported-capability` failure before any device write. Free performs one write and still polls nothing afterwards.
- Report desired power and brightness in snapshots only while an override is active; observation, external control and service evidence stay as today.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `protected-controller-api`: the supported-capability requirement changes from mode-only to power, brightness and scenes with typed constraints; new requirements cover general-control execution, the brightness and power override policy, Free-only scene activation and desired-state reporting.
- `integration-settings-api`: the pure projection additionally lists discovered scene IDs with their user-chosen names; general lighting moves from "unsupported by this extension" to "served by shared v1 with names here".
- `local-mcp-bindings`: wording only; the MCP tool surface still exposes no power, brightness, scene, zone or raw command, but the scenario no longer calls those controller capabilities unsupported.

## Impact

`bridge/controller_state.py` (capabilities, desired state, discovery, one-shot journaling), `bridge/controller_server.py` (admission of the three commands, mode gate), `bridge/bridge.py` (worker loop execution and power gate, override-aware rendering and scene restoration, mode-command reapply), `bridge/integration_api.py` (scene names), tests, `docs/controller-api.md`, `docs/integration-api.md` and `bridge/README.md`. Legacy Windows tray, wall editor and hooks call the same mode functions and keep their behavior. A linked hub companion PR updates the pinned Nanoleaf fixtures, compatibility record and work guide. No installation, device operation, UI, or physical acceptance is included; hub #155 owns hardware acceptance.
