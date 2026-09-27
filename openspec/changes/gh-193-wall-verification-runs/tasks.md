## 1. Application parts (independent of the core)

- [x] 1.1 Demonstrate the missing scenarios, boundary, drive and serve behavior with failing `tests/test_demo_runs.py`, then pass it and the unchanged `tests/test_demo_fixture.py`.
- [x] 1.2 Pass the full Python suite and the unchanged `npm run test:browser` against the restructured demo.
- [x] 1.3 Pass `npm run test:verify`: every reference capture step passes with a screenshot and finalized video, and every negative control fails at its named assertion.
- [x] 1.4 Document the commands, boundary, feature map, negative controls and unsupported cases in the development guide.

## 2. Shared core adoption (after the Hub core release)

- [ ] 2.1 Vendor the released core archive with its checksum and add the `npm run verify --` wrapper around the plug-in; `npm ci` resolves it offline.
- [ ] 2.2 Run `start`, `doctor`, `capture`, `handoff --reset`, `extend`, `stop` and `restart` against real transient units on this host, including two concurrent runs, a failed start and an expired lease, and record the receipts and proof paths in the PR.
- [ ] 2.3 Capture a reference step and a negative control through the core and confirm `passed` and `failed` outcomes and the frozen `verified/SHA256SUMS`.
- [ ] 2.4 Synchronize and archive this change, run the workflow checks, and publish the PR.
