## Why

[Issue #154](https://github.com/jimmie-potts/codex-nanoleaf/issues/154) needs named animation recipes that survive source upgrades and can be replayed through MCP. Today only caller-supplied fields and curated presets are available.

## What Changes

- Store bounded favorites in private installation SQLite with create-only save, atomic collision-safe rename, and explicit delete.
- Freeze supplied fields or a preset into a complete recipe, without capturing live output.
- Add favorite playback and MCP configuration tools while retaining Free-only playback, unchanged snapshot shape, and existing receipts and worker ownership.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `integration-settings-api`: persistent named recipes and configuration commands, plus favorite discovery and playback.
- `local-mcp-bindings`: list, save, rename, forget, and play named favorites through the protected extension.

## Impact

Python effects and integration queue, TypeScript extension contract and MCP bindings, isolated persistence and protocol tests, and owning documentation. No installed state, physical operation, browser feature, or Hub adoption changes.
