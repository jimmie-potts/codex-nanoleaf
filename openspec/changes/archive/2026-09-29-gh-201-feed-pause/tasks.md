## 1. Live pause boundary

- [x] 1.1 Add a held-request regression and observe the missing acknowledgment before implementing pause; retain the actual red result.
- [x] 1.2 Implement paired-only launch control and drained acknowledgment; verify responsive local reads, no new Hub requests, truthful freshness and resume without replay.
- [x] 1.3 Add invalid-file, nonce and ordinary-launch isolation negative controls; verify fixed failures and no diagnostic Hub probe while paused.

## 2. Reseed and handoff

- [x] 2.1 Require matching release before seed and consume it only after successful fresh state; verify refusal paths, lower-owner-revision recovery, ports and token preservation.
- [x] 2.2 Update the owning verification guide and owning `wall-verification-runs` specification; verify protocol examples match the implementation and frozen proof remains unchanged through focused real-manager qualification.

## 3. Delivery validation

- [x] 3.1 Run all applicable source, browser and workflow checks, retaining real results and separating skipped lifecycle tests from owner-host evidence.
- [x] 3.2 Synchronize every affected requirement and archive this complete change before final independent review; verify the resulting specification inventory.
