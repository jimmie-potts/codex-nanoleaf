## Why

The existing wall cache drops connector positions, so the Prism renderer cannot reliably join tubes to hexagonal faces. [Issue #52](https://github.com/jimmie-potts/codex-nanoleaf/issues/52) defines the required additive geometry and compatibility boundary.

## What Changes

- Retain validated connector geometry alongside the existing zone-only cache.
- Add a sanitized connector graph to wall state while preserving existing Line fields and numbering.
- Bound acquisition retries, retain the last valid cache, and document transforms and fallback behavior.

## Capabilities

### New Capabilities

- `wall-connector-geometry`: validated connector/end identities, cache enrichment, and a sanitized drawing projection.

### Modified Capabilities

None. Existing Line identification and wall presentation contracts remain unchanged.

## Impact

The wall server, project geometry helpers, isolated Python/API fixtures, and bridge documentation change. The browser renderer, worker, installation, credentials, and protected machine API remain unchanged. Linux service migration and multi-device geometry remain separately owned work.
