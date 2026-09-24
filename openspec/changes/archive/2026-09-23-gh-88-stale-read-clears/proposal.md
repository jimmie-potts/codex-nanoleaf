## Why

[#88](https://github.com/jimmie-potts/codex-nanoleaf/issues/88): the shared projection keeps a stale session's retained status, so owner read evidence ([Hub #191](https://github.com/jimmie-potts/agent-device-hub/issues/191)) and acknowledgments made elsewhere cannot clear a retained unread task. After a Hub restart every session is uncertain, so those unread tasks keep their Lines, and newer tasks never get one.

## What Changes

- A retained unread task becomes idle when the owner reports its session read, or when every notice is acknowledged for this consumer, even while its evidence is uncertain.
- The transition is steady: no pulse, outward wave or comet. Other retained statuses stay frozen while stale, and a stale unread task does not switch to another displayed status from uncertain evidence.
- The freed task no longer holds its Line, so the existing allocation gives the Line to a waiting task.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `shared-session-consumer`: freshness and effect recovery gains the unread-clearing exception.

## Impact

`bridge/shared_input.py` projection, its tests, and `docs/shared-input.md`. Legacy mode, allocation rules, mode and scene handling are unchanged. Installing into the Linux runtime is a separate, requested step.
