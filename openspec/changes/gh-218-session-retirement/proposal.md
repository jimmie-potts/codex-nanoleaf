## Why

[Hub #218](https://github.com/jimmie-potts/agent-device-hub/issues/218) makes Desktop session ends remove shared monitoring records. Nanoleaf already releases assignments when it observes absence, but it can retain a manual project or task effect when it misses removal and receives a new incarnation of the same identity. This companion consumes the owner's generation metadata to distinguish that case.

## What Changes

- Request snapshot 1.1 and require its per-session generation before projecting validated shared input.
- Validate the unchanged snapshot fields with the checksum-pinned 1.0 Python validator after a narrow version projection; retain validated generation in the existing private envelope.
- Forget task-specific local rows when a generation changes, using the same removal path as authoritative absence. Recreated tasks start with default local presentation.
- Exercise removal, missed removal, restart, empty idle and unavailable-feed behavior with isolated synthetic state and the owner's shared fixture corpus.
- Retain a shared task's row and assigned Line after it becomes read or idle, until authoritative removal or explicit device-local eviction. Reading clears the unread pulse, not its placement.
- Add Evict to the selected task's wall details. Persist eviction for this device and this task incarnation/turn; a new identifiable turn or generation can return with a fresh allocation. The Codex conversation and shared owner remain unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `shared-session-consumer`: generation-aware validation and retirement reconciliation, preserving one owner/writer and global preferences.

## Impact

Affects shared projection, allocation, wall details, focused consumer/browser tests and shared-input documentation. It does not select shared input, install software, change hooks, contact a device or change modes. Hub must support snapshot 1.1 before this reader is activated. Installed and visible-device acceptance remain separately authorized gates on Hub #218. The user approved this presentation expansion during installed acceptance; global eviction is deferred until an owner command is added. Local eviction leaves the owner record counting toward future Work/Free automation.
