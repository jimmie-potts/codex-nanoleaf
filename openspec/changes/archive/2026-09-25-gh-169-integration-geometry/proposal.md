## Why

[Issue #169](https://github.com/jimmie-potts/codex-nanoleaf/issues/169) lets the hub draw the real shape of the Lines and the NL22 Panels without opening Nanoleaf state. Hub #286's physical-layout phase and the shared device art in hub #355 need the element geometry that today only the wall map reads, from the saved `layout.json`.

## What Changes

- Add `GET /controller/integration/v1/geometry?deviceId=<configured-id>`, a read-scoped route of the `nanoleaf.integration/1.0` extension. It answers for every configured device, the Lines and the Panels alike.
- The response carries the device identity, its layout kind, and its elements in the saved order, each with its stable element ID, element number, ordered zone IDs and the display points the wall map draws: three points along each Line, three vertices for each triangle. The controller's global orientation and Y inversion are already applied, as for the map, before the map's Rotate and Flip view options. For the Lines it also carries the connector graph, with each connector's position and the two connectors of each Line.
- A configured device with no saved layout entry answers an explicit empty result: `kind` null, no elements and no connectors. A layout without drawable geometry keeps its elements and sets their points to null.
- The route reads only the saved `layout.json` and one SQLite read transaction. It never discovers geometry, contacts a device, reads the map's drawing cache or writes state. The payload contains no address, credential or private path.
- The extension snapshot keeps its exact 1.0 shape, so the installed hub continues to validate it. The TypeScript consumer adds a closed geometry validator with shared fixtures. A linked agent-device-hub companion adds a sibling hub route that reads and validates this geometry.

Baseline behavior that stays unchanged: the snapshot, commands, receipts, cancellation and animation routes; the wall map's own geometry reads and drawing cache.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `integration-settings-api`: adds the read-only geometry route.

## Impact

`bridge/integration_api.py` (the read view), `bridge/controller_server.py` (the route), `contracts/integration-v1/` (consumer validator and fixtures), tests, and `docs/integration-api.md`. No database migration, no new state and no light write. Source delivery does not install or change the running controller. The design artifact is omitted: this is one pure read route over existing geometry functions, with no state, concurrency, migration or installation change.
