## Context

See proposal.md. A new external package version and shared metadata projection warrant this design under the spec-driven schema.

## Goals / Non-Goals

Use the owner's bounded metadata fields without reimplementing their validation. Preserve local fallback, lifecycle, effects and project preferences. No local Claude transcript reader, live cutover, installation or device work is included.

## Decisions

Use the immutable Agent State 3.3.0 archive and its unchanged Python validator. Keep the consumer's stricter mandatory generation check; the general validator permits omission for compatibility. Request snapshot 1.2 and continue accepting valid generation-bearing 1.1 responses without shared metadata.

Use label, shared title, local Codex title, then provider fallback. Projects retain manual override precedence. A shared project ID retains its existing local key; a name without an ID gets a deterministic hashed key. Updating an identified project's name preserves color and roots. Name-only projects lack rename identity and therefore produce a new key when renamed.

Retain the existing Codex reader because source delivery cannot prove all-session coverage. Issue #100's proposed Claude transcript reader is unnecessary for shared Claude metadata and remains separate; its unresolved local-source decisions do not gate this consumer. Inspection exposes shared metadata but performs no local enrichment or uploads.

## Risks / Trade-offs

- Older owners may reject the 1.2 request: upgrade the owner before the consumer; preserve the last valid projection on failure.
- Name-only projects can share a name: treat the supplied name as their grouping identity, matching the information available from the owner.
- Local fallbacks can still be needed: keep them until a separately verified cutover establishes coverage.

## Migration Plan

Source delivery changes no installation. A later authorized upgrade requires a snapshot 1.2 owner, then this consumer, with the existing explicit source-selection and rollback procedure. The saved generation and task keys remain compatible with generation-bearing 1.1 state.
