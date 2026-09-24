## 1. Qualified navigation

- [x] 1.1 Add legacy wall URL qualification through the configured current title index with red/green Python tests for UUIDs, absent/malformed IDs, index removal and recovery (#108 AC1/AC3).
- [x] 1.2 Add shared root-identity qualification with Python tests for Desktop, CLI, Claude, malformed IDs and folded children; verify wall-only exposure and preserved task/read state (#108 AC2–AC5).
- [x] 1.3 Add the detail anchor, polling refresh and footer explanation with red/green browser tests for href, no target, keyboard activation, narrow layout, URL changes and no map action requests (#108 AC4/AC6).
- [x] 1.4 Document eligibility and read behavior in the bridge guide and inspect the text against the implemented behavior (#108 AC7).

## 2. Acceptance

- [x] 2.1 Run Python, browser and both workflow checks; retain their results outside the candidate commit.
- [x] 2.2 Open a real Desktop thread from an isolated candidate map in a Windows browser and record the observed thread separately from installation/device evidence (#108 AC1/AC5).

Human UI approval and independent review remain delivery gates in the PR. Synchronization/archive requires the applicable implementation and acceptance evidence above.
