## 1. Review corrections

- [x] 1.1 Mark seeded directories and refuse unmarked ones and the installation's state (TDD). Evidence: `StateOwnershipTest` failed before the change, because `serve` ran over both directories, and passes after, with a private HOME.
- [x] 1.2 Refuse ctypes, subinterpreters and the unaudited process launcher (TDD). Evidence: before the change, `test_guard_refuses_spawn_foreign_code_and_subinterpreters` saw every path complete under the guard. After it, each path is refused and recorded, while the unguarded control still reaches the listener by every path.
- [x] 1.3 Start the map's bounded layout retries and tolerate them only in `device-read-refused`. Evidence: `device-read-refused passes when the map retries its layout read during the step` records an in-step retry and passes.
- [x] 1.4 Restrict the `layout-unavailable` check and add `control-device-attempt`. Evidence: the boundary-check unit cases, and the control failing at "no device attempt was recorded during the step" with both refused sends in its record.
- [x] 1.5 Attach the boundary record to failed captures. Evidence: `npm run test:verify` asserts the attachment on every capture, including the controls.
- [x] 1.6 Restart an expired run. Evidence: the lifecycle test asserts the predecessor, the continuity, an unchanged `SHA256SUMS` digest and a refused `handoff`.
- [x] 1.7 Run the Python, browser, verification, lifecycle and workflow checks, redo the delivery evidence run, and record the results in the PR.
