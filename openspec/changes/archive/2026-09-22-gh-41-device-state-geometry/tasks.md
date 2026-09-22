## 1. Registry, layout shape and defaults

- [x] 1.1 Add the device registry reader, per-device layout normalizer and validation; verify a legacy layout loads as `wall`, a version-2 file loads Lines and one-zone triangle elements, a malformed file is rejected without replacing the last valid file, and an address change keeps the identity (focused red then green tests).
- [x] 1.2 Route `load_config`, the installer, the integration reader and the wall map's geometry cache through the normalized shape; verify the existing geometry, integration and Linux runtime tests still pass and the installer writes the new shape.

## 2. Device-scoped state and migration

- [x] 2.1 Add the guarded in-place migration and device columns; verify with the committed pre-change fixture that initialization twice preserves tasks, preferences, scene, active comet, pending edits, mode metadata and controller history and that the second run is a no-op (red then green).
- [x] 2.2 Key placements, comets, preferences, settings, pending edits, Locate, display cache, mode and scene file by device with `wall` as the default; verify equal element ids on two devices, one placement per device, independent modes and scene files, and an unchanged Python suite apart from named-column inserts.

## 3. Documentation and delivery evidence

- [x] 3.1 Write ADR 0009 and link the device-state capability from the README and bridge guide; inspect the rendered text and links.
- [x] 3.2 Run the full Python suite, browser checks, MCP source checks and workflow checks; synchronize and archive this change before final independent review and record the results in the PR.
