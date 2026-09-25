## Why

The wall map still shows only the original Lines device, although [#43](https://github.com/jimmie-potts/codex-nanoleaf/issues/43) runs a second worker for the NL22 Light Panels and [#46](https://github.com/jimmie-potts/codex-nanoleaf/issues/46) put them into service with CLI mode controls only. [Issue #44](https://github.com/jimmie-potts/codex-nanoleaf/issues/44) asks for a selector in the existing map so the operator can see and edit one device at a time from the browser.

## What Changes

- Add a labelled Device selector beside the wall heading, shown when more than one device is registered. The choice is kept in the page URL, and the page opens on Lines. The registered devices are read on every state request, so a device enrolled while the map runs appears without a restart.
- Make the map API device-scoped. `GET /api/state` takes an optional device; the mode, settings, assignment, Locate and eviction actions take an optional `device` field. Untargeted requests keep addressing Lines; unregistered devices are rejected and never fall back to Lines. Project colours and task project assignment stay shared. The protected controller API, integration settings extension and MCP stay Lines-only.
- Show the selected device's mode, pending state, last error, reservations and waiting count. Mode changes address the selected device only.
- Draw a Light Panels device as plain SVG triangles from its cached geometry with static status colours, numbered in the geometry reader's order. Triangles support selection, multi-selection, Project-layout reservation and Shared release, the context card and Locate. Coverage and Swap halves are hidden for triangles and the backend rejects those settings for one-zone elements. Lines keep them.
- Apply Rotate and the flips to the selected device; they are already saved per device.
- Keep the existing protections: selection, refresh and switching send no Locate or effect, display reads use cached geometry, origin and edit-token checks stay, and no response carries a credential. Switching to Panels plays no assembly; the Lines assembly is unchanged.

Unchanged baseline: the Lines presentation, Prism assembly, allocation, reservations, the worker, the device registry and layout shape, the controller wire contract, and the map's read-ownership boundary. Out of scope: showing both devices at once, a "Both devices" action, Prism styling or animation for triangles, and a combined pool ([#47](https://github.com/jimmie-potts/codex-nanoleaf/issues/47)).

## Capabilities

### New Capabilities
- `wall-device-selector`: the device selector and its URL persistence, the device-scoped map API and its defaults and rejections, the selected device's status controls, the triangle view with its supported actions and hidden Lines-only controls, per-device orientation, and the protections that hold across selection and switching.

### Modified Capabilities
- `wall-map-hierarchy`: the default-screen requirement gains the Device selector beside the wall heading when more than one device is registered.

## Impact

`bridge/wall_server.py` (per-request device resolution, device-scoped state and actions, unknown-device rejection), `bridge/project_map.py` (triangle polygons from cached geometry), `bridge/wall.html` (selector, URL, triangle renderer, device nouns, hidden controls, assembly guard), `scripts/demo.py` (registers the synthetic NL22 fixture beside the Lines), new Python and browser checks, the bridge guide, the Linux installation guide and the root README. No worker, database, layout-file, controller-API or MCP change. Source-only; installing the updated map needs a separate request.
