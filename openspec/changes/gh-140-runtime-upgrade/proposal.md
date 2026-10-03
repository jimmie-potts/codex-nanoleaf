## Why

[Nanoleaf #140](https://github.com/jimmie-potts/codex-nanoleaf/issues/140)
replaces repeated manual program swaps with a guarded local upgrade and recovery
command. Fresh Linux setup currently refuses an existing installation and cannot
establish running release identity or compatible recovery.

## What Changes

- Add read-only plan/status and exact-plan upgrade/rollback commands while retaining fresh setup.
- Stage complete immutable Nanoleaf releases behind its existing component paths,
  preserving Hub, shared Node, state, credentials and hook configuration.
- Fence supported entrypoints, stop and verify owned writers, retain consistent
  backups and recover to compatible code without restoring stale state.
- Expose process-bound build identity separately from the strict controller v1 snapshot.
- Consume the published install receipt contract and document standing authority,
  qualification limits and installed completion.

## Capabilities

### New Capabilities
- `runtime-upgrades`: Nanoleaf release plans, provenance, compatibility, admission,
  migration, verified switching, recovery and private receipts.

### Modified Capabilities
None. Existing Linux setup, worker and controller wire contracts remain supported.
The new capability supplies the installed operation boundary around them.

## Impact

Linux installer and owning runtime entrypoints, a separate build-health read,
packaged Python/MCP dependencies, installation documentation, the root agent
pointer and isolated Python/package tests. Contracts 1.2.0 is added solely for
install receipts; controller API 1.0 remains pinned independently. Live state,
devices and host configuration are untouched by source validation.
