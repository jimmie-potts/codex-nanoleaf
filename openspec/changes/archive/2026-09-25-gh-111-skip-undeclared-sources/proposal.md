## Why

Nanoleaf rejects the whole hub snapshot when any session comes from a source missing from `qualifiedSources`. The feed then counts as failed, colors freeze and the wall stops following every agent until the configuration changes. The first Claude Code session posted to the hub would stop the wall. [Issue #111](https://github.com/jimmie-potts/codex-nanoleaf/issues/111) records the requested outcome; #100 depends on it.

## What Changes

- Skip sessions from undeclared sources before presentation instead of rejecting the snapshot. Skipped sessions get no Line, wave, comet, acknowledgment or part in subagent grouping; declared sessions keep updating and the connection stays current.
- Envelope checks keep rejecting the whole snapshot: authentication, version, owner, schema and revision.
- `shared-status` reports a `skipped` object with the skipped session count and their distinct source identities.
- The stored projection keeps only declared sessions, so the wall map, integration API, eviction and acknowledgment never see skipped ones.
- Document how to declare a source such as Claude Code.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `shared-session-consumer`: validated input skips undeclared sources instead of rejecting the snapshot, and inspection reports the skipped sessions.

## Impact

`bridge/shared_input.py` projection, inspection and acknowledgment; `tests/test_shared_input.py`; `docs/shared-input.md`. No new service, dependency, device command, credential path or schema migration. Unchanged baseline: envelope validation, resync behavior, grouping, freshness, eviction and source selection, including the rule that configuration requires legacy input to be selected.
