## Why

[Issue #201](https://github.com/jimmie-potts/codex-nanoleaf/issues/201) supplies the consumer pause boundary needed by [Hub aggregate reset](https://github.com/jimmie-potts/agent-device-hub/issues/557). A live paired consumer must stop reading the old owner before its revision resets, while its local pages and controller keep answering.

## What Changes

- Add a private paired-run pause request and a process-bound acknowledgment after active Hub requests drain.
- Keep local reads responsive and report retained feed freshness truthfully while paused.
- Release the pause during an explicitly authorized paired reseed, after the old process stops and before the fresh process starts.
- Extend verification negative controls and operating guidance; preserve ordinary launches, ports, tokens and frozen proof.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `wall-verification-runs`: add live paired-feed pause, drained acknowledgment and authorized reseed behavior.

## Impact

Changes affect the demo worker, verification plug-in, private runtime controls and paired checks. The shared core and receipt version remain unchanged. Installed services, device behavior and public APIs are outside this source-only change. Hub owns aggregate orchestration and final composition qualification after consuming the accepted revision.
