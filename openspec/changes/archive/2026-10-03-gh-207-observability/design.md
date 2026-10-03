## Context

See proposal.md. The HTTP controller owns request threads; the existing detached worker owns device writes and reads durable command tickets. Its stdout/stderr are discarded. The accepted Python runtime provides bounded queues and explicit context attachment.

## Goals / Non-Goals

Use the accepted package without a new SDK implementation or state migration. Preserve admission deadlines, device retries, scenes, unread state, command output and silent hooks. No browser changes, per-frame logs, live installation or performance qualification.

## Decisions

A leaf diagnostics adapter verifies the immutable package before optional loading. Disabled hosts do not import optional dependencies or start exporters. Controller and worker hosts explicitly own startup, shutdown and queues.

Detached workers use the existing numeric-loopback Collector transport as their configured sink, with local output discarded. This avoids shared log files, retention and multiple file writers. Controller foreground diagnostics may also use stderr. Invalid optional configuration falls back to inert diagnostics without changing domain behavior.

Request spans accept traceparent only after existing authentication and boundary checks. Handler processing success is distinct from a command receipt's outcome. Owned thread handoffs explicitly capture and attach context. Durable worker commands begin a new trace and identify the existing ticket; no trace context is added to SQLite or device requests.

The worker receives an injected adapter. Instrument major native commands and restoration, never frame loops. Export and bounded shutdown happen outside command transactions and deadlines. The shared adapter's queues absorb failures and account for loss.

## Risks / Trade-offs

Collector downtime loses detached diagnostics; shared bounded counters describe loss, with no spool or command retry. This is acceptable for optional local diagnostics. A process restart breaks trace ancestry at durable work; ticket fields support queries honestly. Source tests cover synthetic state and fake transports only.

## Migration Plan

Source-only delivery. Optional host environment settings apply when an operator separately launches or installs the source. Removing those settings disables diagnostics without modifying domain state.
