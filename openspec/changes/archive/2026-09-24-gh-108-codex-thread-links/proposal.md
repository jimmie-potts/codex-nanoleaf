## Why

The wall identifies a task but cannot open its conversation. [Issue #108](https://github.com/jimmie-potts/codex-nanoleaf/issues/108) requests a Desktop thread link in the task detail card, with explicit eligibility and read-state boundaries.

## What Changes

- Add an optional server-built `codexUrl` to eligible wall tasks: indexed legacy Desktop UUIDs and shared Codex Desktop root-session UUIDs.
- Show a keyboard-accessible **Open in Codex** anchor in task details and refresh it when its URL changes.
- Explain selection versus opening in Codex in the footer and bridge guide.
- Preserve task ordering, shared folding, unread ownership, controller/integration APIs, and all device behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `wall-task-inspector`: qualified navigation from the detail card without map actions.
- `shared-session-consumer`: derive a wall-only link from the presented root identity.

## Impact

Wall state projection, shared identity lookup, detail-card rendering, Python/browser checks, and `bridge/README.md`. No schema migration, dependency, installation, hub contract, or guide-publication change. Dependencies #75 and #105 are delivered. Windows navigation acceptance and human approval remain separate delivery gates.
