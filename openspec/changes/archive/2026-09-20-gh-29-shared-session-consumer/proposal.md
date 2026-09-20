## Why

[Nanoleaf #29](https://github.com/jimmie-potts/codex-nanoleaf/issues/29) lets Nanoleaf and Pixoo use one interpretation of qualified agent sessions. The delivered shared core and embedded host now provide the versioned input needed without replacing the Python light writer.

## What Changes

- Add an explicitly selected, persistent shared snapshot consumer with bounded authenticated loopback transport and released Python schema validation.
- Project shared semantic state into existing task allocation and rendering; preserve legacy input until selected cutover and retain explicit rollback.
- Preserve mode, scene, preferences, task epochs and reservations; render stale sessions steadily, never replay old celebrations after reconnect, and expose sanitized health.
- Use the Nanoleaf consumer's clear-on-new-turn policy without inferring readership or success.
- Supply source configuration/CLI and isolated verification. Personal hook installation and physical acceptance remain Hub #8 and Nanoleaf #30.

## Capabilities

### New Capabilities
- `shared-session-consumer`: selection, transport, projection, health, stale behavior and rollback for shared agent input.

### Modified Capabilities
None. Legacy task/scene behavior remains governed by the bridge guide. Shared-mode additions compose with the existing protected controller and Linux runtime contracts.

## Impact

Python bridge/worker, task metadata projection, source tooling, private SQLite additions, released snapshot validator and fixtures, integration documentation and Hub work-guide companion. No provider reducer port, new device writer, personal setup or public-site publication.
