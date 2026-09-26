## Why

[Issue #151](https://github.com/jimmie-potts/codex-nanoleaf/issues/151) adds circular sweeps and one faster speed to the existing Free-mode animation controls. Its encoder and MCP acceptance criteria define source delivery; physical playback needs separate authorization.

## What Changes

- Add clockwise and counterclockwise spatial directions around the saved Line-centroid, plus `faster` at one decisecond per keyframe.
- Publish the additive values in Python and TypeScript validation, animation discovery and MCP schemas.
- Preserve existing encoded animation bytes, default values, limits, Free-only admission and worker receipts.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `integration-settings-api`: accept and discover the new bounded animation values.
- `device-worker`: render circular directions and shorter cycles while preserving old output.
- `local-mcp-bindings`: expose the additive options through the current animation tools.

## Impact

The existing effects module, native TypeScript consumer, MCP enums, fixtures and documentation change. Queueing, persistence, authentication, installation and physical-device ownership do not change. Source merge follows the bundle coordinator's #174 adoption gate.
