## 1. Assembly checks first

- [x] 1.1 Add red-first browser checks for the orb at the bounding-box center, an outward assembly that runs within a second of load and ends within about 2.5 s with exact final geometry, the preference keys and defaults, Replay, no trigger on poll, mode, or layout change, reduced-motion skip, interaction completing assembly and selecting, repeated Replay not queuing, geometry change and connection failure ending assembly, pulses keeping phase, and zero write requests; capture the failing output against the current page.

## 2. Orb and assembly

- [x] 2.1 Draw the persistent orb from `drawWall()` and implement the assembly sequence (adjacency, outward depth, hinged rotation, joint glows, number fade) with the Web Animations API; verify the checks from 1.1 for criteria 1 to 3 pass and the existing 360 number-click and legibility checks still pass.
- [x] 2.2 Implement triggers, preferences, the Replay control, the view-entry integration point, deferred rebuilds, completion on interaction, and ending on geometry change or connection failure; verify the remaining checks from 1.1 pass and the foundation and presentation suites stay green.

## 3. Documentation and integration

- [x] 3.1 Update the bridge guide's map section and ADR 0004; verify links resolve.
- [x] 3.2 Run the Python suite, browser checks, and workflow checks; synchronize and archive this change; record measured rendering cost for the sequence in the PR and leave the PR open for human UI approval.

Task 3.2 evidence: a 2.5 s Chromium trace of one Replay with all 15 Lines
pulsing in Work recorded 18 ms paint, 23 ms raster, 27 ms style, 5 ms layout,
and 21 ms script in total, about 0.5 ms per frame at 60 fps with a heaviest
single paint of 0.46 ms. The trace ran in the headless test browser; an Edge
observation on the Windows PC is part of the human review.
