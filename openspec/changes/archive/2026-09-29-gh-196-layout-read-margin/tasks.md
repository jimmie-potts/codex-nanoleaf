## 1. Layout-read spacing margin

- [x] 1.1 Add boundary-check cases for a read recorded 500 ms late, a map reading on every 1 s poll and a map without the three-read limit, and observe the late read failing before the change (TDD). Evidence: at `4ddf14b` the late read failed with "layout read 2 came 9500 ms after the previous one"; after the change it passes, and the other two fail on spacing and count.
- [x] 1.2 Widen `LAYOUT_READS.apartMs` to 9 s and update the development guide and this delta. Evidence: `npm run test:verify`, including the every-poll map fixture, passes.

## 2. Rebinding guard coverage

- [x] 2.1 Add permanent failing cases for the class-attribute, `import_module`, `sys.modules`, alias, deletion, tuple-target and rebound, imported or indirect `setattr` forms, and observe each pass the old guard (TDD). Evidence: at `4ddf14b` all 12 new mutations returned no problem.
- [x] 2.2 Resolve attribute targets to their root, follow aliases and restrict `setattr`/`delattr` to direct calls. Evidence: every mutation fails the guard, and the current `scripts/demo.py`, with its single `UNAUDITED` loop, passes.

## 3. Delivery validation

- [x] 3.1 Run the Python, verification, browser and workflow checks and record their results in the PR.
- [x] 3.2 Synchronize the delta into `wall-verification-runs`, archive this change and verify the specification inventory before final review.
