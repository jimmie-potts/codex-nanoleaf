## 1. Capture the worker output

- [x] 1.1 Return and persist a latest-only receipt after successful pulse and completion effect sends plus brightness; verify both encoded payloads, physical zone mapping, loop, mode, brightness, and timing fields with focused fake-controller tests.
- [x] 1.2 Preserve the previous successful receipt when an output request fails, including after effect frames were accepted but brightness failed; verify the fake-controller failure leaves the prior receipt intact and the API reports the worker's failed state.

## 2. Expose a passive snapshot

- [x] 2.1 Add `GET /api/rendering` to the existing loopback server using a read-only SQLite connection; verify last-sent, pending, failed, external, and unknown cases, and rejection of writes, through isolated API tests.
- [x] 2.2 Verify repeated reads and map-server restart preserve task, scene, and project state, and do not refresh metadata, acquire geometry, write lights, or advance effects; the read-only connection prevents startup migration or writes.

## 3. Document and complete the specification

- [x] 3.1 Link the new capability contract from the bridge behavior guide and identify #17 as the renderer consumer; verify the documentation link and ownership wording.
- [x] 3.2 Synchronize and archive the issue-linked OpenSpec change; verify every resulting main spec against its delta and run `npm run check:workflow`.

## 4. Validate the source candidate

- [x] 4.1 Run `python3 scripts/check.py` and `npm run test:browser`; retain the actual command results for the PR. Python suite passed on Node 24.21.0; system Node 22 lacks the TypeScript support used by an existing integration test.
