## 1. Application parts (independent of the core)

- [x] 1.1 Demonstrate the missing scenarios, boundary, drive and serve behavior with failing `tests/test_demo_runs.py`, then pass it and the unchanged `tests/test_demo_fixture.py`.
- [x] 1.2 Pass the full Python suite and the unchanged `npm run test:browser` against the restructured demo.
- [x] 1.3 Pass `npm run test:verify`: every reference capture step passes with a screenshot and finalized video, and every negative control fails at its named assertion.
- [x] 1.4 Document the commands, boundary, feature map, negative controls and unsupported cases in the development guide.

## 2. Shared core adoption

- [x] 2.1 Wrap the plug-in with `definePlugin`, add the `npm run verify --` wrapper, use the multi-file artifact and fresh steps, and run the capture checks through the core's `runCaptureStep`.
- [x] 2.2 Pass `npm run test:verify:lifecycle` against real transient units: receipt and identity, doctor, capture, handoff, extend, stop, concurrent runs, a device attempt during start, an early exit, an interrupted start, expiry and restart; confirm it skips with a printed reason without a user manager.
- [x] 2.3 Run the operations with the default roots on this host, capture every step, and record a proof directory, a receipt and doctor output as local evidence.
- [x] 2.4 Replace the pre-release core archive with the released tarball and its checksum, rerun the checks, and record delivery proof from a clean run whose verified set holds only passing reference captures, with the controls captured after handoff.
- [x] 2.5 Synchronize and archive this change, run the workflow checks, and publish the PR.
