## Purpose

Present the bridge's current mode on the wall map itself, with an indicative on-screen status animation that never claims to mirror controller frames and never writes to the bridge or the lights.

## ADDED Requirements

### Requirement: Work shows an indicative pulse

In Work mode the wall map SHALL animate every Line that currently carries a task on a two-second period whose brightness envelope rises during the first fifth of the period, holds until three tenths, falls until half, and rests for the remainder, matching the physical pulse rhythm. Lines without a task SHALL stay steady. The animation SHALL be derived from task status alone and SHALL be described, on the page and in documentation, as an indicative status animation rather than a mirror of physical output. Covers issue #23 AC2 and AC5.

#### Scenario: Active Lines pulse in Work
- **WHEN** the mode is Work and a Line carries a working, question, blocked, or unread task
- **THEN** that Line's halo and core run a two-second pulse and an idle Line does not

#### Scenario: Rebuilds keep the phase
- **WHEN** the page rebuilds the wall because a Line is selected or a poll changes state
- **THEN** each pulse resumes the page-wide phase within 50 ms instead of restarting

### Requirement: Quiet and Free are visible on the wall

In Quiet mode the wall map SHALL show steady Lines with a reduced halo and no running animation. In Free mode the wall map SHALL dim and desaturate the wall and SHALL state that the lights are released to Nanoleaf. Covers AC3.

#### Scenario: Quiet is steady
- **WHEN** the mode is Quiet
- **THEN** no wall animation runs and the halo is fainter than in Work

#### Scenario: Free is released
- **WHEN** the mode is Free
- **THEN** the wall is dimmed and desaturated and the readout says the lights are released

### Requirement: Reduced motion keeps modes distinguishable

When the viewer prefers reduced motion, the wall map SHALL run no wall animation and SHALL still make Work, Quiet, and Free distinguishable by static glow. Covers AC4.

#### Scenario: Reduced motion
- **WHEN** the operating system or browser requests reduced motion
- **THEN** the wall reports no running animations in any mode, and a Work Line with a task shows a stronger static halo than in Quiet

### Requirement: Mode readout

The toolbar SHALL show a readout naming the current mode, the number of physical Lines, the number of tracked tasks, the counts of blocked and question tasks, and whether an edit is pending, refreshed with every poll. Covers AC7.

#### Scenario: Readout follows state
- **WHEN** a poll reports Work, 15 Lines, 5 tasks of which 1 is blocked and 1 is a question, and a pending edit
- **THEN** the readout names Work, 15 Lines, 5 tasks, 1 blocked, 1 question, and the pending edit

### Requirement: Presentation never writes

Rendering a mode, running or stopping the indicative animation, selecting Lines, and displaying the readout SHALL send no light requests, SHALL mark no task read, SHALL change no assignment, and SHALL alter no pulse epoch or scene preference. Covers AC5.

#### Scenario: Watching the wall is passive
- **WHEN** a user switches modes with the existing controls and then only watches or selects Lines
- **THEN** the only requests issued are the existing mode change and state polls
