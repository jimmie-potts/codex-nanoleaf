## Context

See proposal.md for motivation. The extension owns one private queued slot and ticket sequence; the Lines worker processes configuration atomically and journals animation transport separately. Snapshot capability keys are fixed by existing consumers.

## Goals / Non-Goals

Use that owner and queue for persistent recipes. Do not capture current physical output, add a writer, share recipes with the Hub/browser, or modify installations.

## Decisions

- The owner approved create-only save and explicit atomic rename rejecting occupied targets, rather than implicit overwrite or delete-and-create rename.
- Save supplied explicit fields or resolve a preset into full applicable defaults. This preserves meaning when defaults or curated palettes later change; capture would need a separate current-recipe definition.
- Add an idempotently initialized private SQLite table. Revision digests include recipes privately; snapshot fields and capabilities remain unchanged. Favorite configuration operations form a separate command set from advertised snapshot operations.
- Resolve favorite playback against private state during admission and worker encoding, while retaining the original request for replay matching. The single queue slot prevents another favorite edit overtaking playback.
- Favorite edits advance controller configuration revision without marking display state dirty. They return configuration receipts, never transport receipts. Existing authorization, expiry, revocation and hold behavior remains.

## Risks / Trade-offs

- Name collision loses user data if treated as replacement → reject it before admission and recheck inside the worker transaction.
- Defaults drift over upgrades → store complete explicit recipes; retain the database on rollback.
- Layout changes make a recipe too large → apply frame and byte checks at playback and preserve the favorite.
- A lost response leaves the client unsure → original-ticket receipt lookup/replay; no fresh automatic request.

## Migration Plan

Source-only additive table creation on normal database initialization. Reopening and repeated initialization preserve all favorites and existing task/scene state. Older source ignores the table; rollback retains the database. No installed-state migration or fresh setup is performed.
