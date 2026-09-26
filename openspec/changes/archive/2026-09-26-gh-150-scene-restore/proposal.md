## Why

[Issue #150](https://github.com/jimmie-potts/codex-nanoleaf/issues/150) makes stopping a requested animation an explicit restore command using the remembered scene.

## What Changes

- Add a read-only rememberedSceneId to animation options, derived from the saved scene and currently advertised IDs.
- Add a Lines-only MCP restore tool using the existing scene.activate path and caller identity.
- Preserve the shared and extension snapshots, worker ownership and remembered brightness policy.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `integration-settings-api`: expose the remembered scene ID in animation options.
- `local-mcp-bindings`: restore the scene through one explicit existing control.

## Impact

The options projection, MCP binding, tests and guides change. No state migration, controller v1 change, installation or physical operation is required.
