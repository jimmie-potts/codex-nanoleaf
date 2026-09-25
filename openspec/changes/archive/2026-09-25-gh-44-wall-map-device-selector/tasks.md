## 1. Device-scoped map API

- [x] 1.1 Add `tests/test_wall_devices.py` covering the untargeted Lines default, a targeted Panels state with 18 numbered triangle polygons and per-device settings, mode, pending and error, rejection of an unregistered device on reads and actions without a state change, the registry read on each request, device-scoped settings, assignment, Locate and mode, rejected coverage and half-swap settings for one-zone elements, no device contact and no credential in any response, and Lines-only controller and rendering routes. Observe it fail on the current server.
- [x] 1.2 Implement per-request device resolution, `UnknownDevice`, the `device` query and payload handling, `kind` and `devices` in the state, `project_map.triangle_geometry`, and the one-zone rejections. Observe 1.1 pass and `python3 scripts/check.py` stay green.

## 2. Device selector and triangle view

- [x] 2.1 Add `tests/device_checks.cjs` covering the Lines default, the labelled selector, switching and URL persistence across a reload, the Panels' mode and readout, 18 numbered triangles, pointer and modifier selection, keyboard selection and Escape, reservation and Shared release in Project layout, Locate, hidden Coverage and Swap halves, per-device rotation, passive switching and selection, no assembly on the Panels and none replayed on return, reduced motion, the three supported widths, and recovery from an unknown device in the URL. Observe it fail on the current page.
- [x] 2.2 Register the synthetic NL22 fixture in `scripts/demo.py` beside the Lines, implement the selector, URL handling, triangle renderer, device nouns, hidden Lines-only controls and the assembly guard in `bridge/wall.html`. Observe 2.1 pass and the full `npm run test:browser` suite pass, with screenshots of the Panels view at the supported widths.

## 3. Documentation and delivery

- [x] 3.1 Update the bridge guide, the Linux installation guide's enrollment note and the root README; synchronize and archive this change; run `npm run check:workflow` and `npm run test:workflow` and inspect the archived specs.
- [x] 3.2 Run the full Python, browser, MCP and workflow suites on the candidate and publish the PR with the comparison and evidence. Independent Standards and Specification reviews, current-head Depot CI and explicit human approval of the UI candidate remain merge gates.
