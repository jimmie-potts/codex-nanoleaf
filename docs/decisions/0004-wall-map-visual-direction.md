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

### Addendum (2026-09-09): Prism crystal material

Issue #53 replaces the orb and simple stroke material with the approved Prism
finish kit. Thick crystal tubes meet the flat faces of hexagonal connectors.
Bright light cores, long tails, bevels, and broad diffuse spill use the same SVG
components during motion and at rest. The six connector rim sections remain in
place after unfolding. The central connector rotates with its attached structure
as tubes eject and assembly spreads outward through the actual layout.

Work uses two inward packets on each task-active Line, meeting at a center spark
on a shared two-second cycle. Idle Lines stay steady, Quiet lowers the glow and
stops travel, and Free dims and desaturates the crystal. Reduced motion retains
static mode distinctions. Completion of opening, Replay, or interrupted
assembly starts flow at the connectors. Polls and redraws preserve that clock.
These UI clocks remain separate from physical task pulse and comet epochs.

The existing page layout, status colors, allocation controls, local preferences,
keyboard access, and multi-selection remain. Materials load through explicit
local asset paths and use system font fallbacks on the hosting platform. The
renderer releases observers and frames on removal and pauses while hidden.
Issue #26 owns conditional luminous-number visibility and neighbour clearance.
This direction includes no new tray artwork or service migration.

## Consequences

The page uses material and connector shapes derived from the lights it controls.
Motion stays within the wall. Actual and larger-fixture frame measurements and
current-candidate human review establish the practical rendering limits before
merge; no 300-Line performance guarantee is inferred. Status tokens have one home,
which issue #18 can later drive from configurable palettes. The wall map keeps
its own acceptance and human UI approval gate; this decision changes no bridge,
installed state, or physical behavior.
