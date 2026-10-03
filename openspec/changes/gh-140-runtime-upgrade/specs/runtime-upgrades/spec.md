## Purpose

Upgrade and recover the existing Nanoleaf Linux runtime with exact release
identity, preserved state and independently verifiable installed outcomes.

## ADDED Requirements

### Requirement: Exact read-only plan and status
The runtime SHALL provide read-only plan and status commands that distinguish
installed selection, running identity and merged source. Plans SHALL bind the
complete target bundle, baseline, owner, configuration, protected shared paths,
outage, backup and compatible recovery to a digest. Unavailable evidence SHALL
remain unknown; changed bound inputs SHALL require replanning.

#### Scenario: A plan drifts before operation
- **WHEN** installed bytes, configuration, target or protected paths change after planning
- **THEN** upgrade refuses before stopping any service or modifying selection

#### Scenario: The service is inactive
- **WHEN** status observes an inactive service
- **THEN** it reports no running build and does not start a process or contact a device

### Requirement: Verified complete release and compatible recovery
New releases SHALL identify a clean merged full source SHA and verify all payload
and dependency content. Existing releases SHALL be immutable. An unprovable
original source SHALL use an explicit verified legacy identity. The updater SHALL
prove previous-code reopening of target-written state before outage and SHALL
refuse unknown or incompatible recovery.

#### Scenario: Dependency or archive bytes differ
- **WHEN** a shipped file, dependency, manifest or trusted archive hash differs
- **THEN** staging refuses without selecting or starting the candidate

#### Scenario: Previous code cannot reopen target state
- **WHEN** isolated compatibility qualification fails
- **THEN** upgrade refuses before any service stop

### Requirement: Exclusive owned transition
An installation operation SHALL hold an exclusive lock, persist durable intent,
exclude new supported entrypoints and verify all named writers exited before
backup and selection. It SHALL control only Nanoleaf-owned component paths,
services and workers, preserving Hub, shared Node, credentials, hooks and other
history. Every component SHALL resolve through the same selected release.

#### Scenario: A hook races with legacy adoption
- **WHEN** a supported hook or CLI tries to enter old code while adoption is fenced
- **THEN** it cannot become a concurrent writer, and already admitted work drains before selection

#### Scenario: Adoption is interrupted between component links
- **WHEN** first adoption does not complete every owned forwarding path
- **THEN** retained intent and originals describe the incomplete transition and a new operation refuses pending inspection

### Requirement: Running proof and latest-state recovery
Successful installation SHALL verify restarted process identity, bounded wall,
controller and MCP health, and preserved durable state. Build metadata SHALL be
captured from each serving release, separately from controller v1 snapshots.
Candidate failure SHALL recover only verified compatible previous code while
preserving newer state; recovery success SHALL remain a failed requested upgrade.

#### Scenario: The selected directory changes beneath a process
- **WHEN** a running process's selected link changes without restart
- **THEN** that process continues reporting its own original build identity

#### Scenario: Candidate health fails after newer durable writes
- **WHEN** the candidate fails health after writing supported state
- **THEN** recovery reopens the latest state with previous code and never imports the pre-upgrade backup

### Requirement: Durable truthful receipts and retention
Every operation SHALL persist a semantically valid install-receipt/1.0 outcome.
Receipt finalization failure, unresolved intent or failed recovery SHALL prevent
success, automatic retry and pruning. Successful retention SHALL keep current
plus three previous successful owned releases and all referenced, legacy,
receipt, backup and other-owner history.

#### Scenario: Final receipt persistence fails
- **WHEN** the candidate is healthy but its final receipt cannot be durably read back
- **THEN** the command fails, retains the operation barrier and reports finalization failure

#### Scenario: An old release is still referenced
- **WHEN** retention considers a recovery target or another owner's history
- **THEN** it preserves that content regardless of age
