## Why

The wall map now looks like the light installation it controls, but it appears fully formed the instant geometry loads, with nothing to draw the eye to the structure or its center. [Issue #38](https://github.com/jimmie-potts/codex-nanoleaf/issues/38) owns the requested outcome and acceptance criteria 1–10: a brief opening assembly in which the structure unfolds outward from a persistent decorative orb, with browser-local playback preferences and a manual Replay, kept apart from physical effects, celebrations, and status animations.

## What Changes

- Add a persistent decorative orb at the layout's bounding-box center of the wall map. It represents no device and no status.
- Add an assembly sequence of about two seconds: the orb lights, Lines unfold outward from the orb through hinged rotation in outward order (each disconnected section from its own nearest Line), joints glow briefly as Lines settle, and the number tags fade in last. The sequence settles into the current mode's normal appearance and preserves numbering, orientation, selection, and associations.
- Add triggers: first valid geometry load (when the "play on opening" preference is on), a **Replay assembly** control, and a reusable view-entry integration point for future navigation (when the "play on view entry" preference is on). Both preferences are browser-local and default to on.
- Polling, reconnecting, focus changes, Lively pause and resume, layout changes, and mode changes never trigger assembly. Any map interaction completes it immediately and performs its action; repeated Replay does not queue. A geometry change or connection failure ends it immediately. Reduced motion skips it.
- Assembly sends no requests and changes no task, assignment, unread, scene, or pulse-epoch state, and neither restarts nor replays status animations.

Baseline behavior retained unchanged: everything in `wall-line-identification`, the mode presentation and indicative pulse, allocation, modes, Locate, the single-file bundle, the polling contract, and every server route.

## Capabilities

### New Capabilities

- `wall-assembly-animation`: The opening assembly presentation, its orb, its triggers and preferences, its cancellation and completion rules, and its boundary with bridge state and physical effects.

### Modified Capabilities

- `wall-mode-presentation`: The reduced-motion requirement also skips assembly, and the never-writes requirement also covers assembly and its controls.

## Impact

`bridge/wall.html` (orb, assembly sequence, triggers, preferences, Replay control, integration point), `tests/assembly_checks.cjs` (new red-first checks) wired into `tests/browser_checks.cjs`, a race fix in `tests/foundation_checks.cjs`, `bridge/README.md`, and `docs/decisions/0004-wall-map-visual-direction.md`. No API, database, allocator, worker, installer, or dependency change; no controller requests. Delivery is source-only and the UI PR waits for explicit human approval. Coordinates with #15 and #17 only in that the assembly wraps whatever renderer draws the Lines; #19 and #20 remain separate.
