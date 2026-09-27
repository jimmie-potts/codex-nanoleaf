## 1. Review round 2 corrections

- [x] 1.1 Bound the layout reads by count and spacing in the refused-read step and the boundary check (TDD). Evidence: against `e9c6c41`, the timed boundary-check cases and the every-poll map fixture passed where they must fail; both fail as required after the change.
- [x] 1.2 Name a failed seed with a fixed line (TDD). Evidence: against `e9c6c41`, the seed error began "Command failed: <absolute paths>"; after the change it is `demo.py seed failed: Python module wall_server is missing`, and the lifecycle test finds no command or checkout path in the result, receipt or events.
- [x] 1.3 Exit 2 for `seed`'s installation refusal, and tighten the module-dependency guard to a whole-module scan tied to the `UNAUDITED` loop, with the three review mutations kept as failing cases.
- [x] 1.4 Rerun the Python, browser, verification, lifecycle and workflow checks, redo the delivery evidence run at the final head, and record the results in the PR.
