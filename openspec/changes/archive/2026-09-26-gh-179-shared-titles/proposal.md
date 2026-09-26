## Why

[Issue #179](https://github.com/jimmie-potts/codex-nanoleaf/issues/179) makes shared titles and project names available to the wall after Hub #424. The current consumer rejects the metadata-bearing snapshot.

## What Changes

- Pin released Agent State 3.3.0 and request snapshot 1.2.
- Prefer shared titles and projects while retaining existing Codex local fallbacks and manual project preferences.
- Expose allowlisted shared metadata through local inspection and preserve credential exclusions.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `shared-task-metadata`: shared title/project precedence and existing fallback retention.
- `shared-session-consumer`: snapshot negotiation and sanitized metadata inspection.

## Impact

The Python consumer, release pin, wall metadata tests and source guides change. Lifecycle interpretation, grouping, hashed task identity, animation and device ownership stay with their existing owners. Delivery is source-only.
