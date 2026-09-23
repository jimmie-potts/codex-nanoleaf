## Why

[Nanoleaf #72](https://github.com/jimmie-potts/codex-nanoleaf/issues/72) records two Lines held red by uncertain Codex approval markers after the underlying tasks had moved on. The shared owner can explicitly retire a marker, but the consumer currently freezes the old red status even after that authoritative revision.

## What Changes

- Accept a later shared-owner revision that removes an unknown-ID approval on the same turn as explicit recovery, while keeping session freshness uncertain.
- Show `statusEvidence` in the map task projection so a cleared color is not mistaken for fresh provider evidence.
- Preserve assignments, notices, read state and effect suppression during recovery.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `shared-session-consumer`: a bounded exception to steady stale colors after owner-side approval recovery.

## Impact

`bridge/shared_input.py`, `bridge/wall_server.py`, isolated shared-feed tests and the shared-input guide. The Hub recovery operation is owned by [Hub #185](https://github.com/jimmie-potts/agent-device-hub/issues/185). Source changes do not alter an installation or send light requests.
