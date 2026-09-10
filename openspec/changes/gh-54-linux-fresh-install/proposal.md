## Why

[Issue #54](https://github.com/jimmie-potts/codex-nanoleaf/issues/54) removes Windows executable forwarding from the Nanoleaf runtime. Linux processes can reuse the existing SQLite coordination, worker, controller API, and map without a service redesign.

## What Changes

- Add a fresh Linux installer with private state, an isolated Python environment, Linux hooks, configured Desktop JSON readers, and the existing Node MCP host.
- Add fixed wall-map ports and URL-only operation, and honor explicit hook state directories.
- Supply foreground service commands and user systemd units for the map, controller, and MCP host. Preserve the on-demand light worker and existing API behavior.
- Document Linux ownership and the separate installed acceptance in [#55](https://github.com/jimmie-potts/codex-nanoleaf/issues/55); coordinate the architecture guide through [Hub #43](https://github.com/jimmie-potts/agent-device-hub/issues/43).

## Capabilities

### New Capabilities

- `linux-runtime`: Fresh Linux installation, private state, hooks, metadata inputs, service commands, and ports. Maps to #54 A1-A7.

### Modified Capabilities

- `protected-controller-api`: The owning worker and database may be Linux; preserve the existing machine contract and legacy Windows installation boundary.
- `local-mcp-bindings`: Support the existing direct HTTP transport for a Linux-owned controller while retaining Windows compatibility.

## Impact

Python installation and CLI/map startup, Linux MCP configuration, service units, ownership documentation, and capability specifications change. Rendering, allocation, scene behavior, shared contracts, and Windows source remain reusable. No data migration, rollback framework, combined daemon, new hook API, shared monitoring, or new device support is included.
