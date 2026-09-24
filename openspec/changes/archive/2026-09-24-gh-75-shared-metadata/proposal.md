## Why

Shared input currently replaces useful local Codex titles and projects with empty metadata. [Issue #75](https://github.com/jimmie-potts/codex-nanoleaf/issues/75) requires recognizable tasks and correct project allocation before #89's installed cutover.

## What Changes

- Enrich present shared Codex sessions through the existing local metadata reader, preserving owner lifecycle authority.
- Resolve projects as manual override, hub project, then local Codex project; resolve titles as hub label, local Codex title, then provider and session suffix.
- Use the same readable fallback in legacy mode.
- Preserve source switching, retirement, pulse epochs, private metadata and device ownership.

## Capabilities

### New Capabilities

- `shared-task-metadata`: Local presentation enrichment and distinct fallback names for shared and legacy tasks.

### Modified Capabilities

- `shared-session-consumer`: Distinguish provider-qualified local metadata lookup from explicit bindings that preserve presentation continuity. Shared lifecycle authority remains unchanged.

## Impact

Python metadata reader, shared projection, worker polling and wall API fallback; focused Python and browser checks. No shared contract, provider reducer, credential, installation or device transport changes. UI approval is required before merge. Source delivery precedes a separately verified #89 installation.
