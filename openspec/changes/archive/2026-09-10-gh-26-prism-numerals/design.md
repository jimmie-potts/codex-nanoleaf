## Context

See proposal.md for the outcome and ownership boundary. Prism already has persistent label nodes and independent selection, highlight, hover and focus sets. The wall currently forces all numbers visible and uses a temporary label-to-label placement pass. The final crystal is 12.48 units from its centerline; selection reaches 19 and pending reaches 21 including strokes. Reserve a further two screen pixels around all pending envelopes and include the connector rim stroke. These bounds and the current screen transform govern placement.

## Goals / Non-Goals

Keep physical identity and the existing action paths. Add no server-side display state or animation clock. Placement must be bounded and deterministic because it runs when geometry or the viewport changes.

## Decisions

- Solve in screen pixels using actual connector and tube endpoints transformed by the current SVG matrix. A fixed world offset cannot preserve legibility and clearance as the canvas shrinks.
- Reserve measured text plus a minimum 24-pixel click envelope, and clear the outer pending envelope as well as connector bodies. Place all labels together even when most are hidden, so selection does not move neighbouring numbers.
- Try nearby normal and tangent positions before a bounded radial search. Limit search work and return safe placements with an explicit diagnostic for an unexpected impossible canvas. Keep accessible Line controls; never shrink below the text floor or knowingly render overlaps. All required viewport/transform cases must solve completely.
- Keep visibility as a union of reasons. Put show-all in browser-local storage, off by default. Reuse renderer input handlers and the app's existing selection/association code.
- Serve the pure placement helper through one explicit local asset path and include it wherever the existing Prism files are packaged. Avoid a new dependency or generic asset server.

## Risks / Trade-offs

- Font metrics vary by browser and platform. Measure the live numeral core and test viewport containment, minimum size and raw clicks.
- Dense geometry may exhaust candidates. Bound the search, expose unresolved placement, and require complete placement for the accepted actual-layout matrix.
- Geometry refresh can leave stale label transforms. Recompute on geometry or viewport changes, while preserving physical IDs and focus through the renderer.

## Migration Plan

Stack source on Prism PR #58 and renew affected checks when that dependency changes. Publish through a reviewed PR and obtain human approval of the combined UI. Existing installations change only through separately authorized upgrades. Reverting this source restores the preceding always-visible numbering without changing bridge state.
