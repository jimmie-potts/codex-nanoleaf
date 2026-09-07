## 1. Assembly checks first

- [ ] 1.1 Add red-first browser checks for the orb at the bounding-box center, an outward assembly that runs within a second of load and ends within about 2.5 s with exact final geometry, the preference keys and defaults, Replay, no trigger on poll, mode, or layout change, reduced-motion skip, interaction completing assembly and selecting, repeated Replay not queuing, geometry change and connection failure ending assembly, pulses keeping phase, and zero write requests; capture the failing output against the current page.

## 2. Orb and assembly

- [ ] 2.1 Draw the persistent orb from `drawWall()` and implement the assembly sequence (adjacency, outward depth, hinged rotation, joint glows, number fade) with the Web Animations API; verify the checks from 1.1 for criteria 1 to 3 pass and the existing 360 number-click and legibility checks still pass.
- [ ] 2.2 Implement triggers, preferences, the Replay control, the view-entry integration point, deferred rebuilds, completion on interaction, and ending on geometry change or connection failure; verify the remaining checks from 1.1 pass and the foundation and presentation suites stay green.

## 3. Documentation and integration

- [ ] 3.1 Update the bridge guide's map section and ADR 0004; verify links resolve.
- [ ] 3.2 Run the Python suite, browser checks, and workflow checks; synchronize and archive this change; record measured rendering cost for the sequence in the PR and leave the PR open for human UI approval.
