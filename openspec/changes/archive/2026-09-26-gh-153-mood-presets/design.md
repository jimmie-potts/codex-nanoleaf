## Context

The controller and worker already call the same bounded animation encoder. The integration ledger retains the original admitted request for replay. The MCP host forwards validated animation fields.

## Goals / Non-Goals

Expose the ten issue-proposed moods with identical encoding to their explicit parameters. Keep user favorites, future effect candidates, UI controls and palette acceptance on hardware outside this source change.

## Decisions

Keep the static table in `effects.py`; return copies in the options route. Resolve a preset inside `render`, used by admission and worker, without changing the request body or the ledger. This avoids separate resolution paths and preserves replay identity. A preset request allows only `kind` and `preset`; combining explicit fields or overrides is invalid. MCP forwards the name without supplying defaults. The list contains each name as `id` plus its explicit fields; clients can inspect the palette without a second catalogue.

## Risks / Trade-offs

A spatial preset can fail when saved geometry is unavailable, and a larger layout can exceed the byte bound. Existing typed failures and no-write admission checks remain authoritative. Physical palette taste is unverified and requires a separately authorized live review.

## Migration Plan

No state migration. Existing explicit requests and rendering remain unchanged; this change only adds static options and an alternative request shape.
