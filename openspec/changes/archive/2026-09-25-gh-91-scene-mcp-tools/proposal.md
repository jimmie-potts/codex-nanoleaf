## Why

[Issue #91](https://github.com/jimmie-potts/codex-nanoleaf/issues/91) lets Codex play a scene saved in the Nanoleaf app through the local MCP server. The controller already supports `scene.activate` for discovered scenes, in Free mode only ([#64](https://github.com/jimmie-potts/codex-nanoleaf/issues/64)). The local MCP server currently exposes only `nanoleaf_status` and `nanoleaf_mode_set`, and the `local-mcp-bindings` spec forbids scene tools outright. No controller-side change is required: the protected controller's admission, Free-only gate and the `nanoleaf.integration/1.0` snapshot's `scenes` names already exist.

## What Changes

- Add a read tool, `nanoleaf_scenes_list`, that reads the controller's `nanoleaf.integration/1.0` extension snapshot and returns only the advertised `scenes` as `{id, name?}`, ignoring every other field of that snapshot (projects, tasks, settings, wall state). It requires the machine `read` scope, like `nanoleaf_status`.
- Add a control tool, `nanoleaf_scene_activate`, that sends one `scene.activate` command through the existing `/controller/v1/commands` route, passing the caller's `requestId`, `expectedConfigurationRevision` and `expectedGeneration` unchanged, exactly as `nanoleaf_mode_set` does. It requires the machine `control` scope.
- Following hub ADR 0005, activation stays a separate command; the tool never switches mode itself. The existing controller admission rejects activation outside Free mode as `unsupported-capability`, and an unknown scene ID is rejected by the existing controller admission before any device write; both surface as the same typed, replayable failure/receipt shapes already used for `nanoleaf_mode_set`.
- Update the `local-mcp-bindings` specification: the tool surface now advertises exactly the two new scene tools alongside status and mode; power, brightness, zone and raw command remain unexposed.
- Update `docs/local-mcp.md` to describe the two new tools and their scopes.

## Capabilities

### New Capabilities

None. This composes existing `protected-controller-api` and `integration-settings-api` behavior; no controller-side requirement changes.

### Modified Capabilities

- `local-mcp-bindings`: the tool surface requirement changes from "status and mode only, no scene tool" to "status, mode and the two new scene tools; power, brightness, zone and raw command remain excluded."

## Impact

`mcp/src/tools.ts` (two new service extensions and their bindings), `mcp/src/transport.ts` (a `scenes` operation for `GET /controller/integration/v1/snapshot`), `mcp/tests/tools.test.mjs` and `mcp/tests/protocol.test.mjs` (fake-controller coverage for listing, Free activation, Work/Quiet rejection, an unknown scene and scope filtering), `docs/local-mcp.md`. No bridge, controller or database change. Source delivery does not register the server with Codex or touch lights; the owner separately authorizes that per the issue's live acceptance step.
