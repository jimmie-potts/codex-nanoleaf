## Context

The shared consumer freezes task colors while a session is uncertain. That correctly prevents an old approval from clearing on age alone, but also retains red after an explicit shared-owner recovery removes the approval in a later revision.

## Decision

On a validated later snapshot, compare the previous and current session for the same identity and turn. If the previous projection was blocked by an unknown-ID approval and the later owner revision removes blocked attention, allow the semantic status to replace frozen red. Keep the session's stale marker and suppress pulses and comets. The wall map includes `statusEvidence` so status and freshness remain distinguishable. An unrelated input marker cannot trigger this exception.

## Failure and recovery

Invalid snapshots, revisions that do not advance, changed turns and continuing blocked attention keep the existing stale behavior. Feed loss still freezes the latest status. A later fresh approval can restore blocked state. No direct device request or provider permission action is part of this change.
