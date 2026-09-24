## Context

`_project` freezes a stale task's `(turn, status)` unless a specific exception applies: an owner-cleared approval, cleared evidence from current members, or a higher child alert. Retained unread had no exception. Owner read evidence and acknowledgments never refresh lifecycle freshness, so after a Hub restart they could not clear any unread task.

## Decision

Add `unread_cleared`: the retained status is `unread` and the newly computed status is `idle`. `semantic_status` returns idle from unread only when the session is read or has no notice left unacknowledged for this consumer, because an unread task has no alert and no counted activity. The rule applies only to that transition.
- A stale unread task whose uncertain activity now reports active stays unread.
- Retained working, question and blocked stay frozen.
- Partial acknowledgment still leaves the task unread.

The task is recorded as stale. Its activity row and comets are removed as for any stale change, so nothing pulses or replays. `dashboard()` then excludes the idle task from allocation rows, and `allocate` reassigns its Line to the next waiting task.

## Failure and recovery

A later unread observation for a still-stale session remains frozen at idle until current evidence arrives, the same as other retained statuses. A new turn produces current evidence and a normal status. Nothing is written to the owner or to Codex.
