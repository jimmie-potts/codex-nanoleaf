## Context

The legacy installer already owns hook composition through `merge_hooks`, uses the stable `MARKER`, and makes timestamped copies during setup. Shared input selection is implemented in `bridge/shared_input.py`; `bridge/bridge.py` dispatches the shared command family before the ordinary CLI parser.

## Goals / Non-Goals

**Goals:** Reuse the existing hook contract to add an isolated lifecycle, enforce safe source transitions, and keep malformed user configuration untouched.

**Non-Goals:** Change the hub hook, run setup, change installed homes, or verify physical light behavior.

## Decisions

- Put `hooks remove|register --codex-home PATH` in the bridge CLI. An explicit home prevents accidental reliance on environment-specific defaults when managing WSL CLI and Windows Desktop separately.
- Back up the existing bytes to a private timestamped sibling before each actual mutation; avoid creating backups for an idempotent no-op. Use parsed spans to remove or append only marked handler objects, preserving every unrelated JSON entry byte for byte.
- When a backup contains marked handlers, restore those saved handlers instead of synthesizing new ones. This retains each client's platform-specific command during rollback; without a matching backup, register the handler for the command's current platform.
- Parse before writing and perform all checks first. Malformed input or refusal leaves the source file and Nanoleaf state unchanged.
- Check for marked handlers in the configured Codex home before selecting legacy. Report a stable diagnostic that names `hooks register`.
- Keep the feature in the existing `shared-session-consumer` capability. The change adds a lifecycle behavior and strengthens its legacy-selection precondition.

## Risks / Trade-offs

- **A Codex home may be absent or use an alternate JSON layout** → treat a missing `hooks.json` as an empty hook set; reject malformed or structurally invalid JSON before mutation.
- **Windows paths are selected by the caller** → accept an explicit path with `Path` and pass it through the existing platform path conversion where needed; tests use temporary homes on the current platform.

## Migration Plan

After choosing shared input, run `hooks remove --codex-home <home>` for each relevant Codex home. To roll back, first run `hooks register --codex-home <home>`, then `shared-select legacy`. Source delivery alone does not perform this operation.
