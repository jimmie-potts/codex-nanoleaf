# wall-assembly-animation Specification

## Purpose
Open the wall map with a brief assembly in which the structure unfolds outward from a persistent decorative orb, under browser-local preferences and a manual Replay, without touching bridge state or physical lights.

## Requirements

### Requirement: Orb and assembly sequence

The wall map SHALL draw a persistent decorative orb at the layout's hub: the junction where the most Line ends meet, choosing the junction nearest the others when several tie, or the bounding-box center when no Lines meet. The orb SHALL represent neither a physical device nor system status. The map SHALL draw a connector node, shaped like the physical hexagonal connector, at every other junction; connectors SHALL never intercept selection. After valid geometry first loads, the map SHALL play an assembly sequence of about two seconds in which the orb lights, every Line meeting the hub unfolds first and together, each other Line unfolds through hinged rotation into its actual position in outward order, connectors light as the Lines meeting them settle, and number tags appear last. Lines that are not connected to the orb's section SHALL assemble independently in their own outward order. Covers issue #38 criteria 1, 2, and 3.

#### Scenario: First load assembles outward
- **WHEN** the page first receives geometry with the opening preference on
- **THEN** the orb lights at the hub, the Lines meeting it start together, Lines nearer the hub settle before Lines farther away, connectors light as their Lines settle, and the sequence ends within about two seconds

#### Scenario: Hub and connectors
- **WHEN** two junctions join the same number of Lines
- **THEN** the orb sits at the one nearest the other junctions, every other junction shows a connector node, and clicking through a connector still selects the Line beneath it

#### Scenario: Final geometry is exact
- **WHEN** the assembly completes
- **THEN** every Line, number tag, selection ring, and pending ring is where it would be without the assembly, and numbering, rotation, flips, and task and project associations are unchanged

### Requirement: Triggers and preferences

Playback on opening and playback on entering the map SHALL be separate browser-local preferences, both on by default. Opening playback and the **Replay assembly** control SHALL work in the current map; entry playback SHALL be reachable through a reusable integration point for future navigation, named in the bridge guide. Polling, reconnecting, returning focus, pause and resume, Classic and Project changes, and Work, Quiet, and Free changes SHALL NOT trigger assembly. Covers criteria 4 and 5.

#### Scenario: Preferences persist and gate playback
- **WHEN** the user turns off playback on opening and reloads the map
- **THEN** the structure appears complete without assembly, and Replay still plays it

#### Scenario: Routine updates do not replay
- **WHEN** a poll, a reconnection, a mode change, or a layout change updates the map
- **THEN** no assembly starts

### Requirement: Modes and reduced motion

Assembly MAY run in any mode and SHALL settle into that mode's normal appearance. When the viewer prefers reduced motion, the map SHALL skip assembly and SHALL show the completed structure immediately, with the orb present. Covers criterion 6.

#### Scenario: Quiet assembly settles quietly
- **WHEN** assembly plays while the mode is Quiet
- **THEN** the finished wall shows Quiet's fainter steady halo

#### Scenario: Reduced motion skips assembly
- **WHEN** reduced motion is requested and geometry loads or Replay is pressed
- **THEN** no assembly animation runs and the completed structure is visible at once

### Requirement: Completion and cancellation

A map interaction during assembly SHALL complete the assembly immediately and then perform the intended action. Repeated Replay presses SHALL NOT queue sequences. Task lists, alerts, and connection information SHALL remain visible during assembly, and playback SHALL finish into the latest polled state. A geometry change or a connection failure SHALL end assembly immediately. Covers criteria 7 and 8.

#### Scenario: Interaction completes assembly
- **WHEN** the user selects a Line while assembly is playing
- **THEN** the assembly completes at once and the Line is selected

#### Scenario: Geometry change ends assembly
- **WHEN** a poll delivers different Line geometry or the connection fails while assembly is playing
- **THEN** the assembly ends immediately and the map shows the latest state

### Requirement: Assembly never writes

Assembly, Replay, and the preference controls SHALL send no requests other than the existing state polls, SHALL change no physical lights, tasks, assignments, unread state, scenes, or pulse epochs, and SHALL neither restart nor replay ongoing status animations. Covers criterion 9.

#### Scenario: Assembly is passive
- **WHEN** assembly plays or Replay is pressed while Lines carry tasks in Work
- **THEN** no write request is issued and the status pulses keep the page-wide phase throughout
