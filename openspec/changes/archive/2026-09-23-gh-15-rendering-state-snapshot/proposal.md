## Why

Display clients currently have task and mode state, but no record of the most recent animation frames accepted by the Linux worker. [Issue #15](https://github.com/jimmie-potts/codex-nanoleaf/issues/15) provides that source without asking clients to infer output from task state.

## What Changes

- Add a read-only `GET /api/rendering` snapshot to the existing loopback wall-map server, sourced from the sole Linux worker and read without metadata refresh or device access.
- Retain one latest accepted output receipt with physical zone identity, encoded frames, timing, brightness, and send outcome; do not add history, subscriptions, or a second writer.
- Keep current wall-map animation unchanged. Issue #17 owns consuming the snapshot in the visual renderer and checking physical parity.

## Capabilities

### New Capabilities
- `wall-rendering-snapshot`: Expose the Linux worker's latest accepted rendering output and compact outcome to local display clients.

### Modified Capabilities

None.

## Impact

The worker's controller-send path and SQLite state, the loopback wall-map state response, focused Python tests, and the bridge behavior guide. Existing installations create the receipt storage in place without resetting their state. No installer, browser animation, controller API, Windows behavior, or device operation is added.
