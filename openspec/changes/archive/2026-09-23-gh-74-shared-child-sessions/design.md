## Context

The shared snapshot gives each session a full identity, an evidenced `parent` and owner-derived `children` counts of fresh active and uncertain children. Codex subagent hooks carry `agent_id`, so the owner records a separate child session with an unknown turn. Its notices can clear only by explicit acknowledgment. The consumer projected every snapshot session as its own task.

## Decision

Group sessions into presented tasks before projection. A task key is a top-level session: one whose parent is unknown, top-level or ambiguous. Each child joins its nearest top-level ancestor present in the snapshot. The walk up the parents is guarded against cycles. The task status is computed from the top-level session's own activity, notices, read evidence and turn, together with the union of attention across the task. Working also counts the owner's `children.active`, which already excludes uncertain and stale children. The consumer does not interpret provider events or recompute the owner's child counts.

When the top-level session is uncertain, the task is still current if a current child supplies the displayed status: a current child alert, or an owner-counted active child. Otherwise the existing steady-color rule applies. The #72 owner-recovery exception considers approvals from the whole prior task.

A child with no ancestor in the snapshot is presented under its own key, and only while it has blocked or question attention. This keeps an unattributable subagent alert visible without restoring permanent unread children.

## Failure and recovery

Rows of child sessions that the earlier projection created are no longer live, so the existing deletion removes their session, activity, task, comet and slot rows. Other tasks keep their slots, epochs and task preferences. Modes, scenes, Line preferences and device rows are untouched. The freed Lines follow ordinary allocation. Feed loss, invalid snapshots and resync keep their current behavior. Parentage that the owner marks ambiguous leaves the child top-level, which matches the owner's counts. Rolling back the source restores the earlier presentation on the next snapshot, and no stored data migrates.
