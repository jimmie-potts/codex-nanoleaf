## Why

[Issue #33](https://github.com/jimmie-potts/codex-nanoleaf/issues/33) adds local Codex status and mode control through the delivered protected controller. The user selected support for both Windows and WSL. Neither client may become a device writer or open the Windows database.

## What Changes

- Add an opt-in Node 24 foreground MCP host using the immutable Hub #7 package.
- Bind `nanoleaf_status` and `nanoleaf_mode_set` to one configured controller/device. Keep Work, Quiet and Free as the only mode choices and retain the controller's brightness policies.
- Use direct Windows loopback HTTP or a bounded Windows Python HTTP helper from WSL.
- Add separate MCP credentials and dedicated upstream credentials per principal, with immediate checks for revocation on new calls.
- Provide source templates and start, inspect, stop, removal and recovery instructions. Installed-client and light acceptance remain [#34](https://github.com/jimmie-potts/codex-nanoleaf/issues/34).

## Capabilities

### New Capabilities

- `local-mcp-bindings`: authenticated local MCP status/mode tools with Windows-owned admission and bounded Windows/WSL transport.

### Modified Capabilities

None. `protected-controller-api` retains its admission, replay, worker and state requirements. Existing animation and scene behavior remains with the bridge guide.

## Impact

New `mcp/` source package, fake-controller/real-protocol tests and a standard-library Windows HTTP helper. Root npm scripts and workflow checks gain source validation; documentation links to the new specification and ADR 0006. The standalone hub, bridge installation, task monitoring, UI, physical writer and controller schema do not change. CI uses a checked-in verified MCP archive and needs no new private-repository secret.
