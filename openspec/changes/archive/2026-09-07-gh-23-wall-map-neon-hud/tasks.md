## 1. Presentation checks first

- [x] 1.1 Add red-first browser checks for the new capability: a running pulse on task Lines in Work and none in Quiet or Free, no animations under reduced-motion emulation with a stronger static Work halo, phase within 50 ms after a forced rebuild, a readout that matches state counts, a cyan dashed selection ring in Work, and no write requests while watching or selecting; capture the actual failing output against the current page.

## 2. Neon HUD look

- [x] 2.1 Promote the lookbook's Neon HUD token block to `:root`, delete the neutral values, and verify in Edge that only Windows system fonts render with no CSP refusal in the console; verify contrast of body text, muted text, and badges at 4.5:1 or better.
- [x] 2.2 Render the wall as core plus halo strokes without a filter, with the cyan marching selection ring, magenta pending ring, and Locate flash; verify the existing 360 number-click check, the 11 px legibility floor, and no horizontal overflow at 1440, 800, and 390 px still pass.

## 3. Mode presentation and readout

- [x] 3.1 Implement the Work pulse with page-wide phase, Quiet reduced halo, Free dim, and the reduced-motion block; verify the checks from 1.1 pass and Quiet/Free issue no requests beyond the mode change and polls.
- [x] 3.2 Add the `#readout` toolbar strip computed from state; verify it reports mode, Line and task counts, blocked and question counts, and pending state on each poll.
- [x] 3.3 Measure paint per frame in Edge with all 15 Lines active in Work; apply the `steps(20)` or interval fallback if paint exceeds about 4 ms per frame, and record the measurement in the PR.

## 4. Documentation and integration

- [x] 4.1 Update the bridge guide's map description and preview sentence, the root README bullet, and add `docs/decisions/0004-wall-map-visual-direction.md`; verify every link resolves.
- [x] 4.2 Run the Python suite, browser checks, and workflow checks; synchronize and archive this change; attach desktop, compact, and mobile screenshots to the PR and leave it open for human UI approval.

Task 3.3 evidence: a 10 s Chromium trace with all 15 Lines pulsing in Work
recorded about 0.1 ms of paint, raster, style, and layout work per frame at
60 fps, far under the 4 ms budget, so no fallback was applied. The trace ran
in the headless test browser; an Edge measurement on the Windows PC is part of
the human review, and the fallback stays documented in the design.
