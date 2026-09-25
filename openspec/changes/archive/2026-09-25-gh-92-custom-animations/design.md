## Context

A Nanoleaf custom animation is a `display` effect: per-panel frames uploaded once with `PUT /effects` and looped by the device. `effect_payload` in `bridge/bridge.py` already builds such effects for status. The `nanoleaf.integration/1.0` extension ([ADR 0008](../../../docs/decisions/0008-integration-settings-extension.md)) has a bounded request ledger, but so far only for configuration edits. Controller v1 commands pass through the vendored shared contract, and v1 snapshots publish queued commands, so a new kind cannot enter `controller_requests`. The hub's `validateIntegrationSnapshot` checks the extension snapshot's shape exactly, including every capability key and limit.

The owner chose two things on 2026-09-25 at the issue's checkpoint: bounds within the envelope already proven on the device, and a separate read route instead of snapshot changes.

## Goals / Non-Goals

**Goals:** a typed, validated, Free-only `animation.play`; one journaled worker write; a shared frame encoder; MCP list and play tools; bounds within proven device limits.

**Non-Goals:** per-panel keyframes, NL22 Panels, streaming or audio-reactive effects, attention animations over Work status, the hub MCP route, remote clients, and live firmware qualification.

## Decisions

**Extension command, transport receipts.** `animation.play` shares the extension envelope (`apiVersion`, `controllerId`, `deviceId`, `requestId`, `expectedRevision`, `command`) and its ticket sequence, one-queued-request capacity, cancel and receipt routes, expiry and revocation. Its receipts end as `sent`, `failed`, `uncertain` or `cancelled`. Their `priorEffects` value is `confirmed-transmission`, `possible` or `none`, and `physicalOutcome` stays `unknown`. Configuration edits keep `applied`/`configuration`. The alternative, a v1 command, would change the released shared contract.

**Admission.** The controller authorizes, validates the command, then checks the current opaque revision and requires the desired mode to be Free. It renders the effect against the saved Lines layout and rejects it with `capacity` when the effect exceeds the bounds, or with `unsupported-capability` when a spatial pattern lacks positions. Every rejection consumes no ticket. A pending wall edit does not block an animation, because the animation changes no configuration.

**Retirement.** `controller_state.changed(mode=True)` runs for every explicit mode command from the CLI, the wall or a native client. It also cancels queued animations with `stale-generation`, mirroring how v1 cancels queued controls. The worker plays only in Free.

**Journal.** The worker marks the row `attempting` and commits before the send. After it reacquires the write lock, it plays only if the controller generation, the credential and the listener state are unchanged. Otherwise it cancels the row without sending. A send exception finishes the row `uncertain` with `uncertain-result`, then propagates like a failed control, so the existing failure recording and retry apply. Worker startup finishes any row left `attempting` as `uncertain`. The listener never touches `attempting` rows. No row is sent twice, and animations set no controller hold because they are one-shot and never re-derived from desired state.

**Ordering.** In one pass, a pending mode applies first (the Free handoff). Then queued v1 controls and extension animations run oldest first by admission time, so a later scene or animation lands last.

**Encoder.** `bridge/effects.py` owns `display(groups, frames, loop, lines)`, which builds the `display` write from per-zone `(r, g, b, transition)` frames, and the pattern renderers. `effect_payload` keeps its status color logic and uses the shared encoder. The status payload bytes stay identical, and existing tests pin them.

**Patterns.** Frames are keyframes with device-interpolated transitions. Both zones of a Line share frames. The step is 8, 4 or 2 deciseconds for slow, medium and fast.
- `wave` (spatial): 12 keyframes. Each Line's phase is its normalized projection along the direction. Every color gets a traveling crest that blends into the next color.
- `gradient` (spatial): 12 keyframes. The colors spread along the direction and drift with it.
- `pulse`: two frames per color, all Lines together. A one-decisecond flash, then a decay to 10% over two steps.
- `breathe`: two frames per color, symmetric three-step fades between full color and 5%.
- `sparkle`: 12 keyframes. Each Line holds its color, chosen by index, at 25%, and flashes once per cycle at a deterministic offset.

Directions are `left`, `right`, `up`, `down`, `outward` and `inward`, in the controller's layout coordinates before the map's Rotate or Flip view options. `outward` and `inward` are measured from the wall's centroid. Direction is allowed only for spatial patterns. The defaults are `medium`, `right` and looping.

**Bounds.** At most 20 frames per zone and 8,192 request-body bytes (`json.dumps({"write": ...})`). The live-verified middle-Line comet on the 15-Line fixture is 9,009 bytes and 20 frames per zone. A test pins the cap below that comet. The largest request, an 8-color pulse or breathe, fits the 15-Line wall. Larger layouts can reject with `capacity` before queueing.

**Advertisement.** `GET /controller/integration/v1/animations?deviceId=` returns the patterns (each marked spatial or not), speeds, directions, defaults and limits, plus `mode`, `revision` and `nextRequestId`. Read scope is required. It is a pure read in one transaction, like the snapshot. The snapshot's `capabilities` and `limits` stay unchanged for the hub's exact validator.

**MCP.** `nanoleaf_animations_list` returns that view. `nanoleaf_animation_play` sends an extension request built from the caller's `requestId` and `expectedRevision`. Its input schema bounds every field, and it rejects a direction on a non-spatial pattern before dispatch. It returns only a receipt matching the request ticket. An `unsupported-capability` failure carries a message to switch to Free with `nanoleaf_mode_set` and read the list again.

## Risks / Trade-offs

- An unqualified firmware limit might still reject an in-bound effect. The receipt then ends `failed` or `uncertain`, with nothing replayed. Raising the bounds needs a separately authorized live probe.
- `expectedRevision` also covers task associations, so a new task between the list and play calls returns `revision-conflict`. The caller re-reads the list and retries with an explicit new request.
- A power-off override does not suppress animation writes, matching `scene.activate`.

## Migration Plan

No schema change: new rows use the existing `integration_requests` table, and a new `attempting` phase value that older source ignores. Rolling back source leaves such rows unexecuted. They expire or are cancelled as today. Older MCP hosts do not list the new tools.

## Open Questions

None.
