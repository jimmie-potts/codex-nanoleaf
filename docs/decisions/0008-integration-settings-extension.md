# 0008. Nanoleaf-owned integration settings extension

Status: Accepted for source implementation of [#49](https://github.com/jimmie-potts/codex-nanoleaf/issues/49).

## Context

Released controller v1 covers mode commands but not Nanoleaf project reservations,
layout, coverage or task-project overrides. Wall reads include private metadata
and can perform maintenance. Shared-session source delivery supplies neutral
identity mappings, while the shared frontend remains a separate Hub deliverable.

## Decision

Publish `nanoleaf.integration/1.0` at `/controller/integration/v1`, owned by this
repository, with Python and TypeScript consumer fixtures. The user selected this
extension instead of requiring another shared contract release. Keep released
controller v1 unchanged and retain mode commands there.

Use the existing authenticated controller, native-OS private SQLite and single
worker. Extract transaction-level wall application operations for both clients.
Use pure allowlisted reads, opaque local IDs, shared mappings, optimistic revisions
and a separate bounded request ledger. Apply configuration and its receipt in one
transaction. Keep configuration success separate from unknown physical outcomes.

## Consequences

Nanoleaf can deliver its adapter independently of Hub frontend implementation.
Consumers must explicitly support the extension version. Deferred edits need
cancellation and expiry, and newer wall/association changes cause a conflict.
A configuration receipt cannot prove transport or visible lights. Additional
devices, UI, shared contract releases, installations and physical qualification
retain their separate owners. ADR 0007 governs Linux and legacy Windows ownership.
