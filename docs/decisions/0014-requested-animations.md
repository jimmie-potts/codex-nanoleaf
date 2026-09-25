# 0014. Requested animations travel through the integration extension

Status: Accepted for source implementation of [#92](https://github.com/jimmie-potts/codex-nanoleaf/issues/92).

## Context

Codex should be able to play a described animation on the Lines through the local MCP server. The owner chose Free-mode content on 2026-09-23. Asking for an animation first switches the wall to Free with the existing mode command, and nothing restores automatically, as hub ADR 0005 requires. Hub architecture routes arbitrary colors through typed-extension work and rules out raw protocol commands.

Controller v1 commands pass through the vendored shared contract, and v1 snapshots publish queued commands, so a new command kind would change the released contract. [ADR 0008](0008-integration-settings-extension.md) created the Nanoleaf-owned `nanoleaf.integration/1.0` extension for configuration and kept it clear of transport. The hub's `validateIntegrationSnapshot` checks that extension's snapshot shape exactly, including every capability key and limit. No published firmware limit covers custom effect size or frame count.

## Decision

- `animation.play` joins the extension as its one light operation. It uses the extension envelope, ticket sequence, single queued slot, replay, cancellation, revocation and expiry. Its receipts carry transport outcomes (`sent`, `failed`, `uncertain`, `cancelled`) with `physicalOutcome` `unknown`. Configuration edits keep their `applied` receipts.
- The command is accepted only while the desired mode is Free, and every explicit mode command retires a queued one. The controller never switches mode for it.
- The existing Lines worker plays it as one journaled `PUT /effects` display write through a frame encoder it shares with status effects. It records the attempt before the write and never sends it twice. It sends no per-frame stream.
- Options and limits are served by `GET /controller/integration/v1/animations`. The 1.0 snapshot keeps its exact shape, so the installed hub needs no companion change. Animation requests and receipts appear only in the submitting principal's `pending` and `outcomes`, so this holds while the hub keeps its dedicated principal, separate from MCP credentials.
- Effects stay inside the envelope already proven on the device: at most 20 frames per zone and an 8,192-byte request, below the 9,009-byte comet preview that passed live checks. The owner chose this over a live probe on 2026-09-25.

## Consequences

The extension is no longer configuration-only, and its consumers must treat animation receipts as transport evidence. MCP gains a list tool and a play tool without a shared contract release. Larger or longer animations need a separately authorized live probe before the bounds rise. Attention animations over Work status, per-panel keyframes, streaming and the NL22 Panels stay out of scope; they can reuse the encoder under their own decisions.
