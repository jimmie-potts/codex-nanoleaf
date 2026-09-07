# 0005. Protected local controller API

Status: Accepted for source adoption in [issue #28](https://github.com/jimmie-potts/codex-nanoleaf/issues/28).

## Context

The wall server's state read synchronizes metadata and can launch work. Native clients need pure status and separate authentication. The installed bridge owns Windows SQLite state and one light writer; a second ledger database would create admission/desired-state commit gaps.

## Decision

Use an opt-in loopback machine listener and private per-principal credentials. Import the verified shared controller package's Python consumer only at this boundary. Its pinned dependencies are optional for legacy startup. Expose the existing Work/Quiet/Free policy and explicitly reject unsupported generic controls and previews.

Keep controller admission, mode intent, request history and transport bookkeeping in prefixed tables of the existing Windows-owned database. Machine requests, generations and feed cursors have distinct counters from task effects. The single worker journals possible transport effects before sending and retains uncertainty across crashes. Automatic retry cannot replay an uncertain request; deliberate new mode intent can retry.

The [API guide](../controller-api.md) records route wrappers, limits, immutable provenance and the compatibility matrix. The protected-controller specification owns observable requirements; the bridge guide retains current animation/scene requirements.

## Consequences

New machine dependencies are an explicit activation prerequisite. The source installer carries the verified artifact and preserves private state without creating credentials or enabling a new listener. Reads do not refresh device observations. A held uncertain mode requires a deliberate client or operator retry. Existing WSL forwarding remains mandatory, and installation/real-device acceptance remains separate.
