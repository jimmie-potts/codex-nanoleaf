## 1. Connector contract

- [x] 1.1 Add a focused failing fixture check for the missing graph; implement validated connector/end relationships and verify exact IDs, numbering, zone order, transformed positions, and shared housings.
- [x] 1.2 Add malformed and synthetic topology cases; verify unsupported geometry cannot fabricate connections or leak unrelated input fields.

## 2. Cache and wall state

- [x] 2.1 Demonstrate legacy cache enrichment is missing, then implement atomic additive persistence and verify fresh/legacy cache preservation and failed-write behavior.
- [x] 2.2 Add the graph to wall state and bounded retries; verify concurrent readers, privacy, transient recovery, exhausted retries, and existing wall compatibility.

## 3. Acceptance and documentation

- [x] 3.1 Document the versioned projection, transform convention, fallback, and cache ownership; verify links against the implemented contract.
- [ ] 3.2 Run Python, browser, and workflow checks; synchronize and archive every affected spec before the committed candidate's independent reviews.
