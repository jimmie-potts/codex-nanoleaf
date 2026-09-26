## Why

[Issue #153](https://github.com/jimmie-potts/codex-nanoleaf/issues/153) gives common mood requests a curated palette instead of requiring callers to invent one.

## What Changes

- Add the ten proposed presets to the animation options route and MCP listing.
- Accept a preset name as an alternative to explicit animation fields, resolved by the existing server encoder.
- Retain bounds, Free-only admission, replay receipts, and the integration snapshot shape.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `integration-settings-api`: named animation presets in options and play commands.
- `local-mcp-bindings`: preset listing and mutually exclusive preset play inputs.

## Impact

Python effects and animation options, local MCP schema and forwarding, isolated tests and guides. No dependencies, device operations or installations.
