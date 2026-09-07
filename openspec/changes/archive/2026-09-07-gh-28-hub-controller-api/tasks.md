## 1. Verified contract dependency

- [x] 1.1 Vendor the unchanged pinned release and extracted package, preserve the receipt/manifest, and add checksum verification; prove altered archives and package files fail verification before import.
- [x] 1.2 Declare optional pinned controller dependencies and import the shipped Python consumer only when enabled; run every shared fixture ID and prove legacy entry points still start without controller dependencies.

## 2. Durable state and command admission

- [x] 2.1 Add idempotent prefixed controller tables in the existing Windows database and a read-only projection; use an isolated migration fixture to prove existing tasks, activity/comet epochs, unread receipts, slots, reservations and preferences remain unchanged.
- [x] 2.2 Extract transaction-level mode coordination and atomically reserve shared requests with desired changes; use focused red-green tests for exact duplicate/join, conflict, expired/future IDs, retained semantic rejection, capacity ordering and concurrent reservation.
- [x] 2.3 Connect browser/tray mode changes and relevant wall settings writes to controller revisions/generations; prove a stale native client cannot replace a newer browser decision and the existing browser response/protection behavior remains unchanged.

## 3. Protected local API

- [x] 3.1 Add opt-in configuration and credential provision/revoke commands plus the separate loopback listener; exercise actual HTTP for missing/browser/revoked credentials, target/scope failure, exact Host, supplied Origin and Fetch-Metadata rejection.
- [x] 3.2 Serve strict sanitized discovery/snapshot responses and mode-only capabilities; validate emitted envelopes with the shared schema and assert no credentials, addresses, titles or paths escape through success or error responses.
- [x] 3.3 Enforce body/depth/parser, timeout, request-thread, pending and feed concurrency bounds; use hostile request fixtures to prove rejection occurs before reservation or effects and without unbounded thread creation.
- [x] 3.4 Add bounded feed history/recovery and epoch handling; prove retained replay ordering, duplicate suppression, current-cursor empty response, invalid/expired/future/foreign cursor resync, and zero state/effect changes on reconnect.

## 4. Single-worker execution and recovery

- [x] 4.1 Consume accepted mode work through the existing Windows worker with generation checks and durable attempt/result bookkeeping; fake transport tests must prove one writer, cancellation of superseded work and the documented no-op cancellation receipt without fabricated send evidence.
- [x] 4.2 Record successful, failed, partial and uncertain outcomes while retaining last successful-send evidence; inject failure before send, between sub-operations and after a possible send to prove truthful priorEffects and bounded safe failure codes.
- [x] 4.3 Recover pending/in-progress commands and revoked credentials without replaying uncertain requests; fake-clock and restart fixtures must show bounded unavailable-worker failure, explicit retry through a new request and preserved task/effect epochs.

## 5. Source deployment and adoption documentation

- [x] 5.1 Extend source copy/backup/lifecycle tooling for new modules and optional dependencies while preserving private configuration and the supported upgrade path; validate Windows PowerShell tooling with isolated fixtures and no personal installation.
- [x] 5.2 Extend installed WSL forwarding for every new state/configuration command before database access; test Windows dispatch and missing-runtime failure without opening a live Windows database from Linux.
- [x] 5.3 Document routes, capabilities, pending-mode scope, bounds, revocation, no-op/uncertain outcomes, dependency provenance and source-only activation steps; add the lasting ownership/dependency ADR and link the new specification from the bridge guide.

## 6. Cross-boundary verification

- [x] 6.1 Run simulated concurrent machine/browser tests against actual HTTP and the owning queue with isolated state; assert pure reads preserve comet/pulse epochs, unread records, deferred edits, reservations and device-write counts.
- [x] 6.2 Run `python3 scripts/check.py`, `npm run test:browser`, `npm run check:workflow` and `npm run test:workflow`, and add the controller dependency/fixture checks to the existing Python 3.12/3.14 Windows/Linux CI matrix; keep current revision evidence in the PR.

The coordinator's spec synchronization/archive, independent reviews, guarded merge and main-CI/issue readback follow repository delivery policy after these source tasks. They are not implementation checkboxes. No installation, real-client or physical-light result is implied by this checklist.

## Source validation evidence

All 17 source tasks have implementation and isolated validation evidence. Focused
failures preceded immutable contract verification, durable state, HTTP, worker
receipt/recovery and CLI forwarding changes. Further regressions reproduced an
offline status claiming readiness and a Windows 3.14 overload connection reset.
Their fixes preserve unknown offline health and return overload responses before
a bounded connection drain.

The final Python source passes 141 tests on Linux 3.12/3.14 and 140 tests on
Windows 3.12/3.14, where the WSL-only forwarding test is inapplicable. Each suite
executes all 220 shared contract cases. Browser checks, 10 workflow fixtures and
the isolated Windows source-upgrade fixture pass. Runtime dependencies and state
are isolated; source results do not imply personal installation, real-client
connectivity or physical light acceptance. Exact revisions, per-host logs and the
user-approved temporary local-validation exception remain in the delivery record
and PR rather than this source commit.

Review regressions verify held mode intent after intervening reads, coherent
read-only snapshot/feed transactions, deadline-limited admission and commit, and
preservation of validated controller ports during an isolated source upgrade.

The listener retries bounded transient SQLite contention and retains fatal-error
shutdown. Watchdog fixtures cover recovery, expiration and disable after contention.
