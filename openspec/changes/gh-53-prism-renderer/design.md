## Context

See proposal.md for the source boundary. The current wall rebuilds SVG on state changes and uses WAAPI assembly plus CSS pulses. The kit supplies detailed SVG components but needs the accepted two-second rhythm, existing hub rule, per-Line activity, multi-selection and lifecycle behavior. These cross-module animation and asset-security changes warrant a design.

## Goals / Non-Goals

Preserve app operations and physical epoch ownership while replacing presentation. Keep device geometry validation in #52 and final label visibility/clearance in #26. No service setup or controller write path enters the renderer.

## Decisions

- Keep one persistent renderer, update colors/activity without geometry rebuilds, and preserve focus by stable ID on validated replacement. Rebuilding on every poll would lose input state and clock phase.
- Keep assembly progress separate from a shared UI flow clock. Reset flow only at an actual assembly-to-ready transition. Suspend visible elapsed time while hidden; ordinary modes/polls do not restart it. Static states do not schedule frames.
- Use a final-position interaction layer throughout assembly, so immediate completion cannot move the target under a held pointer. Render the same material groups in every pose.
- Consume only the sanitized graph and existing color resolver. Apply presentation rotation/flips once, normalize geometry uniformly, and choose each component's root by the existing most-connected rule. Do not consume raw controller credentials or a controller-first root.
- Serve explicit component filenames and include them in existing packaging lists. A generic directory server would widen file exposure. Preserve a documented standard-Line fallback when exact graph data or components are unavailable.
- Retain all current visible number identities initially; #26 adapts placement and conditional luminous display against final dimensions.

## Risks / Trade-offs

- SVG filter cost grows with layout size → measure the actual 15-Line layout and a named larger fixture; do not claim the schema's 300-Line bound as performance acceptance.
- Detached views can retain animation work → own listeners/observers/frames explicitly and test disposal and hidden resumption.
- Geometry replacement can swap zones or lose selection → fixture checks preserve endpoint/zone order and surviving IDs.
- Local Chromium is unavailable in this execution environment → run the mandatory browser checks in hosted CI and retain the current candidate's visual evidence for human approval.

## Migration Plan

Deliver source through reviewed PRs. Existing installs are unchanged until their owner upgrades. Include portable asset filenames in the #54 handoff; no Linux service implementation is part of this change. Reverting this source change restores the existing renderer without state migration.
