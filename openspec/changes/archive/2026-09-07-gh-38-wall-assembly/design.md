## Context

See [the proposal](proposal.md) for motivation. Each Line is an SVG group of an outline, two halo strokes, two core strokes, and a hit rectangle, drawn from three transformed points; number tags live in a separate group appended last. `drawWall()` rebuilds the SVG whenever a fingerprint of lines, tasks, projects, settings, pending edits, and selection changes, and `anchorPulses()` keeps every status pulse on the document timeline. The fixture's Lines nearly touch end to end (gaps of about 19 units) and form one connected structure around the bounding-box center.

Constraints: single bundled file, no external assets, the existing browser-test contract (15 `.wall-line` groups, untransformed `.number` text, 360 raw number clicks, focus survival across polling), and the existing suites which interact with the map within a second of load.

This design exists because the change introduces a stateful animation that must coexist with one-second polling rebuilds and with the pulse phase contract.

## Goals / Non-Goals

**Goals:** a two-second sequence that reads as outward unfolding, exact final geometry, honest triggers, instant completion on interaction, and no coupling to bridge state.

**Non-Goals:** physical effects, completion celebrations (#19), per-status animation presets (#20), the ambient view (#16), and any change to allocation, modes, or routes.

## Decisions

- Structure from geometry. Endpoints within 40 units are joined. A breadth-first walk from each section's Line nearest the orb assigns an outward depth; the hinge of each Line is the endpoint nearer its parent (or the orb for roots). Alternative: animate by distance only; rejected because it ignores connectivity and would rotate Lines around the wrong end.
- Transforms on the existing groups. Each Line group animates from a folded rotation about its hinge (in user units via `transform-box: view-box`) and zero opacity to identity, using the Web Animations API with an `id` of `assembly`, staggered by depth. Nodes are not duplicated, so the final geometry is exactly what `drawWall()` drew. Joint glows are temporary circles at hinges; the orb is a permanent circle pair drawn by `drawWall()`.
- Rebuilds wait for the assembly. While assembly is active, `drawWall()` returns early and the fingerprint is cleared when the assembly ends, so playback finishes into the latest state and no rebuild can destroy animating nodes. Task lists, badges, readout, and connection text keep updating because they are outside the wall.
- Completion is `finish()`. Any pointer or keyboard interaction on the page outside the Replay and preference controls, any write action, a geometry change (line identities, points, rotation, or flips differ from the assembly's snapshot), or a poll failure calls `finish()` on every assembly animation, removes joints, restores number tags, and redraws. Repeated Replay while active is ignored.
- Triggers are explicit. Opening playback fires once, when `state.lines` first becomes non-empty; Replay and `window.wallAssembly.play('entry')` are the other two entry points. Preferences are `localStorage` keys read on demand with `try`/`catch`; `play('entry')` honors the entry preference and is the integration point for future views.
- Reduced motion. When reduced motion is preferred, `play()` returns without animating; the orb is still drawn.
- Pulses keep phase. Assembly animates group transform and opacity only; pulses on halo and core keep `startTime = 0`, and `anchorPulses()` runs after the redraw at the end.

## Risks / Trade-offs

- Rotating groups intersect neighbours mid-flight → hinges at shared endpoints and ease-out timing keep overlaps brief; the outline track hides most crossings.
- Suites interact within a second of load → any interaction completes assembly instantly, so existing checks see the final geometry; the new checks wait explicitly.
- A rebuild deferred for two seconds could hide a status change → only the wall waits; the task list, badges, and readout update on schedule, and any interaction or Replay-free poll change to geometry completes the wall.
- Transform animation on SVG groups repaints the wall for two seconds → bounded by the sequence length; no filters are involved.

## Migration Plan

No state migration. Preferences are browser-local and absent keys mean on. Update the bridge guide and ADR 0004, synchronize the new capability and the presentation delta, and archive this change on the delivery branch before final review. The source merge does not update the installed bridge.
