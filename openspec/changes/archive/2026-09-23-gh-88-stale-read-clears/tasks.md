## 1. Projection

- [x] 1.1 Clear a stale retained unread task on owner read evidence or full acknowledgment, and keep other stale changes frozen. Evidence: `StaleReadEvidenceTest` in `tests/test_shared_input.py`. The read, acknowledgment and Line-release tests failed before the change and pass after it. The partial-acknowledgment, frozen-working, frozen-question and frozen-blocked, and no-flip-to-working guards pass, and a stale unread parent with a subagent also clears on read evidence. Removing the exception, widening it to working, or accepting any non-unread status each fails a test. Two existing child-session tests used read evidence or acknowledgment as their uncertain change; they now use uncertain activity, keeping their freeze and epoch coverage.

## 2. Documentation and delivery

- [x] 2.1 Update `docs/shared-input.md` for Hub read evidence, session expiry and the stale unread rule.
- [x] 2.2 Run the Python suite and workflow checks; sync and archive this change. Record exact results in the PR.
