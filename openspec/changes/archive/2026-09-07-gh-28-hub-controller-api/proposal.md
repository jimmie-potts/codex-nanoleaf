## Why

Local Codex and the hub need a protected way to inspect Nanoleaf and request its existing modes. [Issue #28](https://github.com/jimmie-potts/codex-nanoleaf/issues/28) owns the outcome and acceptance criteria; this change adopts the delivered [Hub #4](https://github.com/jimmie-potts/agent-device-hub/issues/4) controller contract without changing the current wall editor or installing the integration.

## What Changes

- Add an opt-in loopback machine listener with separately provisioned read/control credentials, immediate revocation, strict target validation and finite resource limits.
- Expose sanitized revisioned snapshots, bounded feed recovery and mode command receipts through controller API `1.0`.
- Advertise Work, Quiet and Free control. Preserve current mode brightness and scene policies; advertise power, brightness, media, zones, scenes and preview as unsupported.
- Add durable controller admission and execution bookkeeping to the Windows-owned bridge database. Route mode requests through the existing worker and preserve task/effect epochs, unread tracking and reservations.
- Pin and verify the immutable private `@jimmie-potts/device-contracts` `1.0.0` archive, import its Python consumer only for the enabled machine listener, and test the owning HTTP/worker implementation against the shared corpus.
- Supply source configuration and upgrade tooling that preserves installed WSL forwarding. Activation, personal credential provisioning and physical testing remain separate authorized work.

## Capabilities

### New Capabilities

- `protected-controller-api`: authenticated local machine status/control, durable admission, pure reads, bounded recovery and preserved worker ownership.

### Modified Capabilities

None. The existing wall specifications retain their behavior. The bridge guide continues to own the current animation and scene contracts; this change adds the machine-client contract and links its new owner.

## Impact

New controller modules and tests; focused changes to `bridge/bridge.py`, the state-changing entry points in `bridge/wall_server.py`, source installation/backup tooling, Python dependency declarations, CI and adoption documentation. `bridge/wall.html` and tray presentation need no changes. Dependencies are optional for legacy startup and pinned for machine API use. CI consumes checked-in verified artifact content without sibling checkouts or cross-repository secrets.
