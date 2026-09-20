## 1. Contract and pure reads

- [x] 1.1 Define the finite versioned contract, ADR and consumer fixtures; verify Python/TypeScript agreement and unchanged shared v1 fixtures.
- [x] 1.2 Implement pure bounded projection; verify private canaries, stable local/shared identities and byte-unchanged reads with device/metadata calls forbidden.

## 2. Protected edits

- [x] 2.1 Extract common wall operations and implement scoped revisioned admission; verify success, duplicate/conflict, malformed, foreign principal/target and concurrent wall/native tests.
- [x] 2.2 Process queued configuration edits in the existing worker with expiry/cancellation/revocation; verify active comet, pending wall edit, lost response, restart, launch failure and preservation tests.

## 3. Integration and delivery evidence

- [x] 3.1 Expose authenticated HTTP routes and package modules in Linux/Windows source paths; verify HTTP guards, retained forwarding and isolated packaging tests.
- [x] 3.2 Update controller/integration docs and Hub guide companion; inspect matrix/versioning/rollback and run guide checks.
- [x] 3.3 Run full Python, browser and workflow checks; synchronize/archive the complete specification before independent final review.
