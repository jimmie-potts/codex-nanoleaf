## Why

[Issue #49](https://github.com/jimmie-potts/codex-nanoleaf/issues/49) needs machine access to existing task-display configuration without exposing private wall metadata or browser credentials. Shared session identities are now available from #29.

## What Changes

- Add a Nanoleaf-owned `integration/v1` contract and Python/TypeScript consumer fixtures. Keep the immutable shared controller v1 archive and schema unchanged.
- Add pure, sanitized, revisioned configuration reads and authenticated settings, reservation, task-project and color writes through common wall application operations.
- Track bounded request identity, pending configuration, conflicts, cancellation and configuration effects independently of physical transport evidence.
- Document the operation/permission matrix, native Linux and retained Windows paths, rollback and consumer boundaries.

## Capabilities

### New Capabilities
- `integration-settings-api`: protected machine inspection and editing of existing Nanoleaf task-display configuration.

### Modified Capabilities

None. Released mode commands, wall behavior, input selection and rendering policy retain their contracts.

## Impact

Controller listener/state, wall application operations, existing worker configuration processing, isolated tests and integration guides. The Hub guide gets a linked companion. No frontend UI, installation, hooks, additional device support or physical acceptance is included.
