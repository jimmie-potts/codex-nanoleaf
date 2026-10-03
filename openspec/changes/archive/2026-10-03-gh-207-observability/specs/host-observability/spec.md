## Purpose

Provide optional common diagnostics for Nanoleaf controller and worker operations while preserving device ownership and command behavior. Scenarios map to [#207](https://github.com/jimmie-potts/codex-nanoleaf/issues/207).

## ADDED Requirements

### Requirement: Verified optional host diagnostics

The controller and worker SHALL use the accepted versioned diagnostic artifact and shared query fields. Diagnostics SHALL require explicit enablement, retain separate machine output and use bounded host-owned queues. Detached worker diagnostics SHALL reach the explicitly configured local Collector without changing hook output.

#### Scenario: Disabled and enabled hosts
- **WHEN** a host starts with diagnostics disabled or explicitly enabled
- **THEN** disabled operation imports no optional telemetry dependencies and enabled operation emits canonical startup, shutdown and major operation records through its configured sink

#### Scenario: Packaged consumer
- **WHEN** copied package bytes are consumed outside the producer checkout
- **THEN** immutable archive, manifest and file verification and shared conformance succeed, while corrupted bytes are rejected

### Requirement: Honest correlation and outcomes

Diagnostics SHALL accept remote trace context only after existing authentication on owned boundaries, carry context explicitly across owned thread handoffs, and preserve actual command receipt outcomes. Persisted cross-process work without trace context SHALL start a new trace and use existing ticket fields for correlation.

#### Scenario: Concurrent requests and worker handoff
- **WHEN** authenticated requests execute concurrently and a detached worker later executes persisted work
- **THEN** request contexts remain isolated, owned thread work is correlated, and worker records link the command ticket without claiming request trace parentage or physical success

### Requirement: Diagnostic failure does not change domain behavior

Unavailable, slow or invalid diagnostic sinks SHALL NOT change command admission, results, retry policy, one device writer, scenes, unread state or source reservations. Diagnostic queues, loss counters and shutdown SHALL retain the shared runtime bounds.

#### Scenario: Collector failure
- **WHEN** fake-device operations run with an unavailable or stalled Collector
- **THEN** the same effects and domain outcomes occur once, diagnostic loss remains bounded and accounted, and host shutdown respects the shared budget
