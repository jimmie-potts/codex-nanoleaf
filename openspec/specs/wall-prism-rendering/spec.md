# wall-prism-rendering Specification

## Purpose

Render the actual Nanoleaf Lines layout with reusable crystal components while retaining the wall map's identity, local interaction and protected data boundaries.

## Requirements

### Requirement: Scalable crystal material
The wall SHALL use the approved Prism material for both moving and finished components: thick faceted tubes, bright cores with long tails, broad diffuse spill and hexagonal connectors joined on flat faces. Each Line SHALL keep two independently colored zones resolved from existing task status, project signatures and half assignments. Covers issue #53 AC1 and AC3.

#### Scenario: Same material through motion
- **WHEN** an active Line assembles and then carries inward light
- **THEN** its bevels, crystal body and diffuse spill use the same components as the finished pose, with the correct color at each endpoint

### Requirement: Validated layouts and identity
The map SHALL consume the versioned connector projection, preserve stable Line numbers and zone ownership, and apply only presentation rotation and flips in the browser. Valid replacement SHALL retain selection and current colors for surviving IDs. Invalid or unsupported geometry SHALL retain the last valid layout; with none available, the standard Line map SHALL remain usable with an explanatory fallback. Covers AC6 and AC7.

#### Scenario: Alternate topology
- **WHEN** the saved layout, a chain, branch, cycle or disconnected fixture is rotated or flipped
- **THEN** connector-face joins, topology, relative lengths and physical identities remain correct

#### Scenario: Geometry replacement fails
- **WHEN** a malformed graph arrives after valid geometry
- **THEN** the existing layout and surviving interactions remain available without invented connector relationships

### Requirement: Local interaction survives rendering
The wall SHALL preserve keyboard focus, Ctrl/Command/Shift multi-selection, task/project/inspector associations, selection and pending rings, explicit Locate, and Classic/Project allocation semantics. The renderer SHALL NOT add state or device writes. Luminous numerals SHALL follow the wall identification visibility and clearance contract. Covers issue #53 AC6 and issue #26 AC3, AC4 and AC6.

#### Scenario: Select during an update
- **WHEN** a poll or material update occurs while a Line is focused or several Lines are selected
- **THEN** the same physical IDs retain focus/selection and no Locate, unread, assignment or light request is issued

#### Scenario: Selection interrupts assembly
- **WHEN** an interaction selects a Line before assembly finishes
- **THEN** the structure settles immediately, the intended physical Line is selected, and its current numeral is visible in the completed layout without a stale label or discarded action

### Requirement: Bounded portable assets
Drawing assets SHALL load only through explicit local paths with correct content types and retained Host, origin, token and CSP protections. A foreground Linux wall server SHALL serve the packaged components without Windows helpers or remote asset dependencies. Covers AC8.

#### Scenario: Asset access is bounded
- **WHEN** a client requests an approved component path or an arbitrary/traversal path
- **THEN** only the approved component is served and no private file or configuration is exposed

### Requirement: Rendering lifecycle and evidence
Replacing or removing a renderer SHALL release its listeners, observers and frames. Hidden hosts/documents SHALL pause motion at the current position; visible resumption SHALL continue it. Quiet, Free and reduced-motion steady states SHALL have no unnecessary animation loop. Actual-layout and larger-fixture frame measurements SHALL name the tested size and browser, with no inferred 300-Line support. Covers AC9.

#### Scenario: Hide and dispose
- **WHEN** a moving wall is hidden, revealed, replaced and removed
- **THEN** motion resumes at its paused position and no obsolete observer, listener or frame continues after disposal
