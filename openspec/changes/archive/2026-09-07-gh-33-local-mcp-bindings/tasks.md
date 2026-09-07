## 1. Prepare immutable dependencies and planning

- [x] 1.1 Verify merged #28 and released Hub #7, record the MCP archive/source/checksum receipt, and verify installed package and bundled contract manifests. Completion: corruption and isolated consumer checks pass without sibling checkout access.
- [x] 1.2 Adopt ADR 0006 and this exact issue-linked change through the repository wrapper. Completion: current status/instructions and spec validation succeed with the expected capability inventory.

## 2. Implement local configuration and transport

- [x] 2.1 Add strict opt-in configuration and principal credential loading using focused red/green tests. Completion: malformed, oversized, duplicate, missing and rotated credentials reject as designed, including scope changes between authentication and dispatch.
- [x] 2.2 Add fixed-loopback Windows HTTP and WSL Windows-Python transports. Completion: fake-controller tests cover exact routes, paths with spaces, proxy/redirect refusal, missing runtime, input/output/deadline bounds and safe errors without state/device access.
- [x] 2.3 Add explicit foreground listener/startup/shutdown. Completion: disabled startup, exact path/Host/Origin, native absent Origin and shutdown-after-admission fixtures pass without terminating controller work.

## 3. Bind supported tools

- [x] 3.1 Add fixed-target status and mode extensions with shared schemas and result validation. Completion: discovery shows only authorized supported tools; invalid destinations/capabilities/identity fail before dispatch; all modes and exact receipts pass.
- [x] 3.2 Cover replay, conflicts, stale revisions, concurrent callers and failure recovery. Completion: real protocol tests on both supported versions preserve identity and uncertainty with one upstream attempt, including cancellation/disconnect and invalid/late responses.

## 4. Document and qualify

- [x] 4.1 Add Windows/WSL Codex templates and private configuration examples, start/inspect/stop/removal and credential/recovery instructions. Completion: examples parse and commands agree with inspected CLI syntax; documentation clearly assigns real installation/client/device evidence to #34.
- [x] 4.2 Add source validation to scripts/workflow, preserve legacy behavior and run affected platform checks. Completion: Node 24 Windows/Linux, Python 3.12/3.14 Windows/Linux, browser and workflow checks pass under the user's local-validation exception; evidence stays in the PR.
- [x] 4.3 Synchronize and archive the exact change before fixed-head review. Completion: current wrapper lookups and strict validation pass, every affected specification matches its delta and all source tasks have evidence. Independent reviews and guarded merge follow under the delivery workflow.
