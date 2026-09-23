## Why

[Nanoleaf #74](https://github.com/jimmie-potts/codex-nanoleaf/issues/74) investigates the growing count of shared unread tasks on the wall map. At owner revision 808, 33 of the 69 unread tasks were Codex subagent sessions. The shared owner records each subagent under its own child identity, with the parent evidenced and the turn unknown. Its turn-ended notice never clears on a new turn. The consumer presents every child as an independent task, so each subagent adds a permanent unread indicator and can hold a Line. Legacy hooks attributed subagent events to the parent session, and the Hub's own Tidbyt consumer gives children no row.

## What Changes

- A session with an evidenced parent is part of its nearest top-level ancestor's task. It is not a separate task.
- A child's blocked or question attention, and the owner's count of its fresh activity, raise the parent task to blocked, question or working. A child's turn-ended notices do not make the parent unread.
- Current child evidence that supplies the displayed status keeps an otherwise uncertain parent current, so a fresh subagent approval is not frozen behind the parent's older color.
- A child whose ancestor is absent from the snapshot is presented alone, and only while it has blocked or question attention.
- Child task rows left by the earlier projection leave on the next snapshot, which frees their Lines for waiting tasks.

Top-level notices, read evidence, acknowledgment and the new-turn policy are unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `shared-session-consumer`: subagent sessions join their parent task for presentation and freshness.

## Impact

Changes `bridge/shared_input.py`, the isolated shared-feed tests and the shared-input guide. The guide also records the per-notice recovery path for top-level notices retained without read evidence. Qualified Codex Desktop read evidence belongs to the shared owner and is tracked upstream. Source changes do not alter an installation or send light requests.
