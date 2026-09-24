# wall-mode-presentation Specification

## Purpose
Present the bridge's current mode on the wall map itself, with an indicative on-screen status animation that never claims to mirror controller frames and never writes to the bridge or the lights.

## Requirements

### Requirement: Work shows an indicative pulse

In Work mode the wall map SHALL send one bright packet from each connector toward the center of every Line carrying a working, question, blocked or unread task. Packets SHALL meet in a brief center spark during a shared two-second UI cycle. Both ordered zones SHALL retain their app-resolved colors. Lines without a task SHALL stay steady. The animation SHALL be derived from task status alone and SHALL be described, on the page and in documentation, as an indicative status animation rather than a mirror of physical output. Covers issue #53 AC3–AC4 and retained issue #23 AC2 and AC5.

#### Scenario: Active Lines pulse in Work
- **WHEN** the mode is Work and a Line carries a working, question, blocked, or unread task
- **THEN** both zones flow inward on the two-second cycle and an idle Line does not

#### Scenario: Rebuilds keep the phase
- **WHEN** the page rebuilds the wall because a Line is selected or a poll changes state
- **THEN** each active Line resumes the page-wide phase within 50 ms instead of restarting

### Requirement: Quiet and Free are visible on the wall

In Quiet mode the wall map SHALL show steady Lines with a reduced halo and no running animation. In Free mode the wall map SHALL dim and desaturate the wall and SHALL state that the lights are released to Nanoleaf. Covers AC3.

#### Scenario: Quiet is steady
- **WHEN** the mode is Quiet
- **THEN** no wall animation runs and the halo is fainter than in Work

#### Scenario: Free is released
- **WHEN** the mode is Free
- **THEN** the wall is dimmed and desaturated and the readout says the lights are released

### Requirement: Reduced motion keeps modes distinguishable

When the viewer prefers reduced motion, the wall map SHALL run no wall animation, SHALL skip the opening assembly and show the completed structure immediately, and SHALL still make Work, Quiet, and Free distinguishable by static glow. Covers issue #23 AC4 and issue #38 criterion 6.

#### Scenario: Reduced motion
- **WHEN** the operating system or browser requests reduced motion
- **THEN** the wall reports no running animations in any mode, no assembly plays, and a Work Line with a task shows a stronger static halo than in Quiet

### Requirement: Mode readout

The toolbar SHALL show a live status readout, refreshed with every poll, that names the current mode with its short explanation, states whether an edit or mode change is pending, and names the counts of blocked and question tasks when either is above zero, otherwise that there are no alerts. The Line total SHALL appear once, at the wall heading, and the task total once, at the Tasks heading, rather than in the readout. Covers issue #23 AC7 and issue #78 AC3.

#### Scenario: Readout follows state
- **WHEN** a poll reports Work, 15 Lines, 5 tasks of which 1 is blocked and 1 is a question, and a pending edit
- **THEN** the readout names Work with its explanation, the pending edit, 1 blocked and 1 question
- **AND** the wall heading names 15 Lines and the Tasks heading names 5

#### Scenario: Quiet without alerts
- **WHEN** a poll reports Quiet with no blocked or question tasks and no pending edit
- **THEN** the readout names Quiet with its explanation and says there are no alerts, without repeating the Line or task totals

### Requirement: Presentation never writes

Rendering a mode, running or stopping the indicative animation, playing or completing the assembly, selecting Lines, and displaying the readout SHALL send no light requests, SHALL mark no task read, SHALL change no assignment, and SHALL alter no pulse epoch or scene preference. Covers issue #23 AC5 and issue #38 criterion 9.

#### Scenario: Watching the wall is passive
- **WHEN** a user switches modes with the existing controls, replays the assembly, and then only watches or selects Lines
- **THEN** the only requests issued are the existing mode change and state polls
