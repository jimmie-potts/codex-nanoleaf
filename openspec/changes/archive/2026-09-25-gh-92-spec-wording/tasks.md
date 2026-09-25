## 1. Review corrections

- [x] 1.1 Clear the transport hold when an animation is admitted (TDD). Evidence: `test_admission_clears_a_transport_hold_like_a_fresh_native_request` failed before the change (hold row still present) and passes after.
- [x] 1.2 Correct the Free handoff wording in the device-worker spec and the matching README text. Evidence: the synced spec and `bridge/README.md` agree with the worker's Free-mode writes.
- [x] 1.3 Run `python3 scripts/check.py`, `npm run test:mcp` and the workflow checks, and record the results in the PR.
