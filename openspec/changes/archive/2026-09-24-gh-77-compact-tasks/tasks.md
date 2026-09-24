## 1. Compact and full inspection

- [x] 1.1 Reproduce the 72-task unbounded/duplicate list in a failing browser test, implement the original eight-row default (superseded by section 3) and single waiting summary, and observe the same test pass (AC1, AC3).
- [x] 1.2 Implement priority and full-list status/waiting/text filters with truthful shown/global counts; verify 0/8/72 fixtures, stable ties, every-task reachability, and no writes (AC1, AC2, AC5).

## 2. Interaction and acceptance

- [x] 2.1 Test and preserve selection, focus, scroll, details and override interactions across status/placement/retirement/recreation, including filtered selection recovery (AC2, AC3, current-session boundary).
- [x] 2.2 Verify unknown metadata, long labels, narrow/reduced-motion rendering and existing interaction journeys; update the bridge guide link and run full browser plus workflow checks. Synchronize/archive the completed capability before independent review; human UI approval remains a pre-merge gate (AC4, AC5).

## 3. User-requested Line-count grid refinement

- [x] 3.1 Reproduce the old eight-row cap against fifteen Lines, implement a snapshot-derived limit (including zero and changing Line counts), and observe the focused browser check pass.
- [x] 3.2 Fit fifteen compact tiles in two desktop columns without task scrolling at 1440×900 and 1280×800, before and after selection and with waiting/long labels; preserve full-list access, focus, overrides and narrow layouts. Verify by geometry assertions and screenshots.
- [x] 3.3 Update the guide and synchronized specification, archive the complete revised change, run browser/workflow checks. Both renewed reviews, current-head CI and human UI approval remain post-archive delivery gates for the revised candidate.
