## MODIFIED Requirements

### Requirement: Reduced motion keeps modes distinguishable

When the viewer prefers reduced motion, the wall map SHALL run no wall animation, SHALL skip the opening assembly and show the completed structure immediately, and SHALL still make Work, Quiet, and Free distinguishable by static glow. Covers issue #23 AC4 and issue #38 criterion 6.

#### Scenario: Reduced motion
- **WHEN** the operating system or browser requests reduced motion
- **THEN** the wall reports no running animations in any mode, no assembly plays, and a Work Line with a task shows a stronger static halo than in Quiet

### Requirement: Presentation never writes

Rendering a mode, running or stopping the indicative animation, playing or completing the assembly, selecting Lines, and displaying the readout SHALL send no light requests, SHALL mark no task read, SHALL change no assignment, and SHALL alter no pulse epoch or scene preference. Covers issue #23 AC5 and issue #38 criterion 9.

#### Scenario: Watching the wall is passive
- **WHEN** a user switches modes with the existing controls, replays the assembly, and then only watches or selects Lines
- **THEN** the only requests issued are the existing mode change and state polls
