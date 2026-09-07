## Why

The wall map controls a glowing light installation and sits behind a neon tray icon, yet it renders as a muted navy dashboard whose wall shows only static status colors. [Issue #23](https://github.com/jimmie-potts/codex-nanoleaf/issues/23) owns the requested outcome and acceptance criteria AC1–AC10: the user chose the "Neon HUD" look from a three-way lookbook built on the real page markup, so the page should match the product it controls and show the mode it is in.

## What Changes

- Replace the neutral token set introduced by #22 with the Neon HUD tokens: near-black grid, cyan and magenta neon chrome, monospace readouts, translucent bordered cards with bracket corners, cyan number tags. Fonts stay within the Windows system set because the map server's Content Security Policy blocks web and data-URI fonts.
- Render the wall as a bright core stroke plus a wide halo stroke per half, without a CSS filter, with a cyan marching-dash selection ring, a magenta pending ring, and a one-second Locate flash.
- Add an indicative status animation: in Work, Lines with a task pulse on the physical two-second envelope; Quiet shows steady Lines with reduced halo; Free dims and desaturates the wall. Reduced-motion preferences disable every wall animation while modes stay distinguishable. The animation approximates the rhythm from status alone and is documented as such; exact mirroring of controller frames stays with #15 and #17.
- Add a toolbar readout that names the mode, Line count, task count, blocked and question counts, and pending state from the polled state.
- Update the bridge guide and root README, and record the visual direction in a decision record.

Baseline behavior retained unchanged: physical numbering, badge groups, selection, inspector and pending wording (`wall-line-identification`), allocation, modes, Locate restrictions, the single-file bundle, the polling contract, and every server route.

## Capabilities

### New Capabilities

- `wall-mode-presentation`: How the wall map presents Work, Quiet, and Free on screen, including the indicative pulse, reduced-motion behavior, the mode readout, and the boundary that presentation never writes to the bridge or the lights.

### Modified Capabilities

None. `wall-line-identification` requirements are unchanged; its scenarios remain covered by the existing checks.

## Impact

`bridge/wall.html` (tokens, wall rendering, animation, readout), `tests/foundation_checks.cjs` (new red-first checks), `bridge/README.md`, root `README.md`, and `docs/decisions/0004-wall-map-visual-direction.md`. No API, database, allocator, worker, installer, or dependency change; no controller requests are added. Delivery is source-only and the UI PR waits for explicit human approval.
