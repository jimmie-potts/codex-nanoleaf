# ADR 0004: Wall map visual direction

Status: Accepted

Date: 2026-09-07

## Context

The wall map renders a physical light installation and is launched from a neon
blue and green tray icon, but it looked like a muted navy dashboard whose wall
showed only static status colors. A review on 2026-09-06 produced a lookbook of
three directions on the real page markup: a clean control panel, a neon HUD, and
a hybrid. The map server's Content Security Policy allows no web or data-URI
fonts, so any direction must use Windows system fonts. Issue #22 fixed the
layout and state-visibility defects first, independent of any look.

## Decision

Adopt the neon HUD as the wall map's visual identity: near-black with a faint
cyan grid, cyan accent and selection, magenta for pending edits, Bahnschrift
body text, Cascadia Mono readouts and Line numbers, translucent bordered cards,
and a luminous wall drawn as a bright core plus a wide halo stroke without CSS
filters. In Work, Lines with a task pulse on screen on the physical two-second
envelope as an indicative status animation; Quiet is steady with a fainter halo;
Free dims the wall. Reduced-motion preferences stop every wall animation while
keeping the modes distinguishable. The pulse is derived from task status alone
and is never presented as a mirror of controller frames; exact mirroring belongs
to the authoritative rendering work in issues #15 and #17. Presentation sends no
light requests and changes no task, assignment, epoch, or scene state.

## Consequences

The page matches the product it controls and the tray icon. Motion is confined
to the wall, so its cost is bounded and measured before merge, with a stepped or
interval fallback if paint exceeds the budget. Status tokens have one home,
which issue #18 can later drive from configurable palettes. The wall map keeps
its own acceptance and human UI approval gate; this decision changes no bridge,
installed state, or physical behavior.
