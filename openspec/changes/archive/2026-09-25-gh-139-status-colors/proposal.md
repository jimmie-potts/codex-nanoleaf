## Why

In Work mode the unread pulse uses the same blue as the unused-Line base, so at 30% brightness a finished task waiting for review is hard to tell from an empty Line. Status colors are fixed constants in the worker and fixed tokens in the wall map; only project colors can be edited. [Issue #139](https://github.com/jimmie-potts/codex-nanoleaf/issues/139) records the owner's accepted palette and the customization scope.

## What Changes

- Store one task-light palette (Base, Working, Question, Blocked, Unread) in private SQLite, shared by every registered device. Rows exist only for roles the operator changed, so an upgraded installation starts with the new defaults: dim blue `#0A1866` base and violet `#9B30FF` unread.
- The worker reads the palette on every pass instead of the fixed `BASELINE` and `COLORS` values. Pulses, outward waves, Quiet's steady colors, the comet tail, Project-layout status halves, empty Shared Lines and Panels triangles use it. Alert priority stays keyed by status. The comet head, the Locate flash, Free and the no-scene fallback blue are unchanged.
- `/api/state` reports the effective palette. The existing validated `/api/settings` write accepts a partial palette or a reset to the defaults, all or nothing, with the existing host, origin and token checks. The integration settings API, CLI, controller API and MCP gain no palette operation.
- The wall map's Options menu gains a Colors group: a choice per role with suggested swatches and a custom color, Reset colors, and a similar-color warning. The wall artwork, legend, Project halves sample and status labels use the effective palette.
- Migrate the task-light color contract from the bridge guide into a new `task-light-colors` capability spec.

## Capabilities

### New Capabilities

- `task-light-colors`: the status-to-color contract for Work, Quiet, Project layout, comets and Panels, the stored palette and its defaults, the settings write, and the map's effective colors.

### Modified Capabilities

- `wall-map-hierarchy`: the Options requirement gains the Colors group and its request boundary.
- `panels-rendering`: triangle status and idle colors follow the shared palette instead of fixed hues.
- `shared-session-consumer`: idle shared Lines use the base color instead of fixed blue.

## Impact

`bridge/bridge.py` frame colors, the display cache key and preview; `bridge/project_map.py` palette storage; `bridge/wall_server.py` state and settings validation; `bridge/wall.html` tokens, legend and Options menu; `scripts/demo.py`; Python frame, API and migration tests; a new browser check; the bridge guide. No new service, dependency, device command or credential path. The unchanged baseline: status priority, pulse timing, wave and comet timing, reservations, halves, coverage, orientation, mode, scene and brightness handling.
