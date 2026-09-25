## Why

Two retained requirements still describe the retired Windows runtime after [issue #131](https://github.com/jimmie-potts/codex-nanoleaf/issues/131)'s main change: the shared consumer's qualification evidence asks to "preserve legacy Windows routing", and a controller scenario lists the tray as a mode-command source. Independent review of PR #138 flagged both; this companion change corrects the wording so no specification presents Windows routing or the tray as supported.

## What Changes

- `shared-session-consumer`: the "Source qualification evidence" requirement no longer asks to preserve legacy Windows routing.
- `protected-controller-api`: the "Mode command supersedes a queued control" scenario names browser, CLI and native mode commands; the tray no longer exists.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `shared-session-consumer`: wording of the qualification-evidence requirement.
- `protected-controller-api`: wording of one scenario under "General controls execute through the single worker queue".

## Impact

Specification text only. No code, test or behavior change; the tests that cover these requirements are unchanged.
