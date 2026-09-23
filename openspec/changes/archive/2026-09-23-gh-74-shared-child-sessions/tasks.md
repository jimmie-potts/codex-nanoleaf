## 1. Subagent presentation

- [x] 1.1 Reproduce children presented as separate retained unread tasks, and a fresh child alert frozen behind an uncertain parent. Then group children into their parent task. Evidence: the focused `ChildSessionTest` presentation, roll-up, freshness and retained-row tests failed before the implementation and pass afterward.
- [x] 1.2 Cover the notice lifecycle with a child present: genuine unread, qualified read evidence, explicit acknowledgment, a new turn under clear-on-new-turn, uncertain evidence and resync. Assert the map count and Line allocation at each step. Evidence: `ChildSessionTest.test_notice_lifecycle_follows_documented_count_and_allocation`.
- [x] 1.3 Keep an orphan child's alert visible without restoring its unread notice, and group children the same way whatever the snapshot order, including with a missing top or a parent cycle. Evidence: `ChildSessionTest.test_child_without_its_parent_shows_only_attention` and `test_grouping_does_not_depend_on_snapshot_order`.
- [x] 1.4 Derive task freshness from the members that supply the displayed status. A resolved current child alert clears under an uncertain parent, and an alert held only by uncertain children stays steady under a current parent. Evidence: `test_resolved_child_alert_clears_under_an_uncertain_parent` and `test_uncertain_child_alert_stays_steady_under_a_current_parent` failed on the first candidate and pass afterward. The child-origin #72 recovery, grandchild and ambiguous-parentage tests cover the remaining paths.

- [x] 1.5 Rank retained and newly supplied statuses, so that a higher subagent alert escalates steadily over a retained or current lower status. Evidence: `test_uncertain_child_alert_is_not_hidden_behind_a_retained_color` and `test_uncertain_child_red_escalates_past_a_current_question` failed on the round-two candidate and pass afterward.
- [x] 1.6 Make working follow the owner's fresh active count, so a silent subagent never holds its parent. The parent's idle state, turns and completions show normally, and an uncertain parent keeps its last color. Evidence: `test_silent_subagent_follows_the_owners_active_count`, which fails against the round-four candidate's hold.

## 2. Documentation and validation

- [x] 2.1 Document subagent presentation, retained top-level notices and the per-notice recovery path in the shared-input guide. Evidence: `docs/shared-input.md` names the new-turn, dashboard and CLI acknowledgment paths and their credential requirement.
- [x] 2.2 Run the Python, browser and workflow checks; validate, synchronize and archive this change. Record exact results in the PR.
