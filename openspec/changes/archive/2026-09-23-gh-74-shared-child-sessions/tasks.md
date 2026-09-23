## 1. Subagent presentation

- [x] 1.1 Reproduce children presented as separate retained unread tasks, and a fresh child alert frozen behind an uncertain parent. Then group children into their parent task. Evidence: the focused `ChildSessionTest` presentation, roll-up, freshness and retained-row tests failed before the implementation and pass afterward.
- [x] 1.2 Cover the notice lifecycle with a child present: genuine unread, qualified read evidence, explicit acknowledgment, a new turn under clear-on-new-turn, uncertain evidence and resync. Assert the map count and Line allocation at each step. Evidence: `ChildSessionTest.test_notice_lifecycle_follows_documented_count_and_allocation`.
- [x] 1.3 Keep an orphan child's alert visible without restoring its unread notice. Evidence: `ChildSessionTest.test_child_without_its_parent_shows_only_attention`.

## 2. Documentation and validation

- [x] 2.1 Document subagent presentation, retained top-level notices and the per-notice recovery path in the shared-input guide. Evidence: `docs/shared-input.md` names the new-turn, dashboard and CLI acknowledgment paths and their credential requirement.
- [x] 2.2 Run the Python, browser and workflow checks; validate, synchronize and archive this change. Record exact results in the PR.
