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

### Addendum (2026-09-07): opening assembly

Issue #38 adds a decorative orb at the wall's hub (the most connected junction,
nearest the others on ties), hexagonal connector nodes at every other junction to
echo the physical connectors and the tray icon, a light sheen along each Line, and
a two-second opening assembly in which the Lines meeting the hub unfold first and
the rest follow outward through hinged rotation, connectors lighting as their
Lines settle. The orb represents neither a device nor status. Playback on opening and on view entry are browser-local preferences,
both on by default, with a manual Replay; nothing else triggers it. Any
interaction completes it, reduced motion skips it, a geometry change or lost
connection ends it, and it sends no requests and alters no task, assignment,
unread, scene, or pulse state. It is a presentation flourish kept apart from
physical effects, celebrations, and status animations.

## Consequences

The page matches the product it controls and the tray icon. Motion is confined
to the wall, so its cost is bounded and measured before merge, with a stepped or
interval fallback if paint exceeds the budget. Status tokens have one home,
which issue #18 can later drive from configurable palettes. The wall map keeps
its own acceptance and human UI approval gate; this decision changes no bridge,
installed state, or physical behavior.
