## Why

After selecting shared input, legacy Codex hooks remain registered and perform avoidable startup and SQLite work on every event. Removing them manually currently risks changing unrelated hooks, while the existing uninstall path also changes device modes; rollback likewise has no safe command that restores just this integration's hooks.

## What Changes

- Add explicit Codex-home commands to remove and restore only the Nanoleaf-marked hooks, with a private backup and no mode, task, or device changes.
- Require registered legacy hooks before selecting legacy input and refuse hook removal while legacy input is selected.
- Document the supported cutover and rollback order.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `shared-session-consumer`: define safe marked-hook removal and restoration and the source-selection safeguards.

## Impact

Changes the Python CLI and shared-input selection guard, temporary-home tests, and shared-input/Linux installation guidance. It does not remove the hub hook or perform installed cutover or physical acceptance. See [issue #89](https://github.com/jimmie-potts/codex-nanoleaf/issues/89).
