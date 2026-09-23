## 1. Consumer recovery

- [x] 1.1 Reproduce uncertain approval red and prove that a later owner revision removing it clears the projection without a comet. Evidence: focused `RecoveryTest.test_owner_recovery_clears_stale_red_without_clearing_other_state` failed before the implementation and passes afterward.
- [x] 1.2 Expose uncertain status evidence on map tasks and document the owner-side recovery boundary. Evidence: the focused test checks `statusEvidence`, and the guides describe the permission and installation limits.

## 2. Validation

- [x] 2.1 Run the Python, browser and workflow checks; validate and archive this change. Record exact results in the PR.
