## Context

See [the proposal](proposal.md) for motivation. After #22 the page's CSS is layered (`tokens, base, layout, components, states`) with a token set that reproduces the old navy look, `data-status` on wall groups and badges, `data-mode` and `data-style` on the body, and a `.glow` stroke under each `.zone` that is currently zero-width. The approved lookbook (issue #23) already contains the Neon HUD token block on the same markup, so this change is mostly token values plus the animation, the readout, and documentation.

Constraints: the server's CSP allows no external or data-URI fonts (system fonts only; Bahnschrift, Cascadia Mono, Consolas, and Segoe UI are installed on the target PC); the page must remain a single bundled file; `/api/state` carries no frame or comet data; the browser checks pin ids, classes, data attributes, aria labels, exactly 15 `.wall-line`s, untransformed `.number` text at 11 px or more, 360 raw number clicks, and focus survival across polling.

This design exists because the change adds motion with a performance and accessibility surface and touches presentation policy that #15 and #17 will later refine; no backend, state, or installation behavior changes.

## Goals / Non-Goals

**Goals:** ship the chosen look on the existing structure; make the mode legible on the wall; keep the animation cheap, phase-stable, and honest about what it represents; keep every existing check green.

**Non-Goals:** mirroring physical frames or timing (#17 via #15), comet or celebration rendering (#15, #19), configurable palettes (#18), per-status animation presets (#20), the inspection-only display and ambient view (#12, #16), any new controller polling, and any runtime theme switch (the alternative looks are deleted).

## Decisions

- Halo as a stroke, not a filter. A wide low-opacity `.glow` line under each core `.zone` replaces `drop-shadow`. Animating opacity on plain SVG strokes repaints cheaply; filtered elements would re-rasterize every frame across 30 segments. Alternative considered: keep the filter and animate it; rejected for cost.
- Pulse in CSS, phase from the document timeline. `@keyframes` on the halo and core mirror `pulse_amplitude` in `bridge/bridge.py`. After every render the page sets each pulse animation's start time to zero on the document timeline, so fingerprint rebuilds, mode changes, and motion-setting changes resume the exact page-wide phase. A negative `animation-delay` computed before the style flush was tried first and lagged by one or two frames. Alternative considered: per-task phase from `task.started`; rejected because poll jitter limits fidelity and the animation is indicative, not a mirror.
- Indicative, not authoritative. The animation keys off `data-status` only. The readout says "indicators on", never "live" or "mirroring"; the bridge guide states the map does not replay waves or comets. This keeps #17's future renderer free to replace the animation source without changing the styling.
- Mode through tokens. `body[data-mode]` selects halo opacity and core opacity in Quiet and a saturate/brightness filter on the whole SVG in Free (one composited layer, static). The wall fingerprint stays mode-independent.
- Reduced motion. A `prefers-reduced-motion: reduce` block disables every wall animation and raises the static Work halo so modes remain distinguishable.
- Cost gate with a fallback. Measure paint per frame in Edge with all 15 Lines active. If it exceeds about 4 ms, switch the timing function to `steps(20)` (10 fps, matching `PULSE_TICKS`) or drive one custom property from a 100 ms interval; record the measurement and the choice in the PR.
- Selection and pending rings. Cyan dashed ring with a marching animation in Work for selection; magenta dashed ring without motion for pending; a one-second white flash for Locate. Under reduced motion the selection ring is static.
- Readout element. A new `#readout` in the toolbar computed in `render()` from `state`; no existing test references it.

## Risks / Trade-offs

- Glow bleeding into small text → glow lives only on the wall SVG; text sits on solid or translucent panels with contrast checked at 4.5:1 or better.
- "Everything glows" flattening the status signal → status hues stay the brightest elements; chrome accents are cyan and magenta at lower luminance.
- Animation cost on a persistent display → measured before merge with the documented fallback; #14 records a resource baseline for later comparison.
- Users reading the pulse as a live mirror → wording on the page and in docs, and the capability spec, say indicative; #17 owns parity.
- Test fragility from timing → checks use `getAnimations()` and computed styles rather than screenshots, and phase checks allow 50 ms.

## Migration Plan

No state migration. Delete the unchosen token blocks. Update the bridge guide's map description and the sentence that the map is not a frame-by-frame preview, plus the root README bullet; add the decision record. Synchronize the new capability and archive this change on the delivery branch before final review. The source merge does not update the installed bridge.
