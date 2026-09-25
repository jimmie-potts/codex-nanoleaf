## Context

See proposal.md. `wall_server.App` loads one configuration for the original Lines device at startup, acquires connector geometry for it with a bounded retry budget, and every state read and action uses that configuration for its device and element ids. `project_map.geometry` projects two-zone Lines into map points; one-zone elements have no map geometry. `bridge/wall.html` draws the Lines through the Prism renderer, falls back to a standard SVG wall, keeps one global selection, and names everything a Line. `load_config` may contact a device when no valid saved layout exists, and ADR 0010 keeps Panels discovery out of the map. The private configuration and `layout.json` already hold one registry entry and one layout entry per device, and `map_settings`, `line_prefs`, `map_pending`, `locate` and the mode keys are keyed by device.

## Goals / Non-Goals

**Goals:**

- One page and one API that address the selected device, defaulting to Lines and rejecting unknown devices.
- A triangle view drawn from cached geometry through the same selection, inspector, reservation, orientation and Locate paths as the Lines.
- No device contact from display reads, no new light writer, and no change to the Lines presentation or assembly.

**Non-Goals:**

- Showing two devices at once, a shared selection across devices, or a device-keyed page model (design note in the issue; [#119](https://github.com/jimmie-potts/codex-nanoleaf/issues/119) moves the rebuild policy behind a view model first).
- Prism styling, pulse, wave or comet animation for triangles.
- Device targets for `/api/rendering`, the controller API, the integration settings extension or MCP.

## Decisions

- **Per-request device resolution in the map server.** `App.device_config(device)` returns the startup configuration for the default device and, for any other registered device, a configuration built only from that device's saved `layout.json` entry (`devices.projection`) with its id and kind. It reads the registry from `config.json` on each call, so enrollment needs no restart, and it never calls `load_config` or `light_request` for a non-default device; a registered device without a saved entry reports a geometry error. An unregistered device raises `UnknownDevice`, a `ValueError` subclass, which the handler turns into a 400 whose body also lists the registered devices. Alternative rejected: caching per-device configurations, which would need invalidation on enrollment and removal for no measurable gain at one poll per second.
- **API shape.** `GET /api/state?device=<id>`; actions carry an optional `device` field that the server removes from the payload before the existing validation, so the existing payload checks are unchanged. The state keeps its `lines` element list for compatibility and adds `kind` and `devices` (id, kind, readable name, default flag). Untargeted requests use the default device. `/api/project` and `/api/task` stay shared; a `device` on them is validated and otherwise ignored. Alternative rejected: a separate `/api/devices` endpoint, since the state and the rejection already carry the list.
- **Triangle polygons on the server.** `project_map.triangle_geometry` turns each cached triangle into three vertices at radius 150/√3 from its centroid, at angles 90° + `o` + k·120°, then applies the global orientation and the display Y inversion exactly as `geometry` does for Lines. The fixture's rows alternate `o` 0 and 60 with centroids two inradii apart, which only fits an apex-up reading of `o` 0; ADR 0010 lists the physical up/down meaning as unconfirmed, so the human UI approval compares the map with the wall. Numbers are the elements' saved numbers, which the reader assigns by position.
- **One dispatch point in the page.** `drawWall` keeps its Prism and standard-wall paths for `kind` lines and adds a triangle path for `kind` panels that draws inset polygons with the status fill, a thin edge that carries the selection, focus, pending and Locate states, and a centred number. Selection, `inspect`, task rows, badges, pending text and Locate work on element ids and are unchanged apart from the noun (Line or Triangle), taken from `state.kind`. Coverage and Swap halves hide for triangles, and the legend's halves note hides too. Alternative rejected: one renderer for both shapes now; the Lines are drawn by Prism's crystal renderer, and the issue records the unified renderer as a design note for the later B.U.N.N.Y. page, not as a criterion.
- **Selector and URL.** A `Device` control sits in the wall heading row and is hidden while one device is registered. Choosing a device clears the selection and fingerprints, destroys the Prism renderer, updates the URL with `history.replaceState` (the default device removes the parameter, so Lines URLs and the existing browser routes stay as they are), and polls the new device. Assembly plays only for the Lines kind; a page that opens on the Panels plays the opening assembly when Lines geometry first appears, as the assembly specification already requires. A rejected device in the URL shows the server's message and fills the selector from the rejection so the operator can recover.
- **One-zone rejections in `apply_operation`.** A `coverage` setting or a `signature` edit for a configuration whose kind is not lines raises `ValueError`, before any write. The integration settings extension calls the same function with the Lines configuration and is unaffected.
- **Demo and fixtures.** `scripts/demo.py` writes a registry and a version-2 layout with the Lines and the synthetic 18-triangle NL22 fixture into its temporary state, allocates the synthetic tasks on both devices, and applies each device's mode revision, so the browser suite can switch devices against real server code without a device. Python checks use the two-device layout from the device tests with `light_request` patched to fail.

## Risks / Trade-offs

- [The `o` orientation reading is unconfirmed on hardware] → display-only; the fixture is self-consistent, and the UI approval compares the map with the physical Panels.
- [A URL parameter changes the poll URL, and the browser suites intercept `**/api/state`] → the default device carries no parameter, and the new suite returns to Lines and clears the parameter before it ends.
- [The heading row gains a control at 390 px] → the Device caption is visually hidden at phone width like the other captions, and the hierarchy widths are asserted with the Panels selected.
- [Two processes read `layout.json` per poll] → the file is small and already read by `layout_generation` per poll; a malformed file makes only the non-default device report a geometry error.
