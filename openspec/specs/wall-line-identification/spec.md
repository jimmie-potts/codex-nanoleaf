# Wall Line identification

## Purpose

Connect each physical Nanoleaf Line to its current task and project throughout the wall map, with consistent numbering and selection that does not control the lights.

## Requirements

### Requirement: Stable physical Line numbers

The page SHALL use the same number for the same physical Line in every view. Rotation, either flip, and layout changes SHALL preserve the mapping between physical Lines and numbers. Numbers SHALL NOT represent project identity, reservation counts, or task counts. This retains the map's existing physical numbering and extends it to the rest of the page. Covers issue #6 AC1.

#### Scenario: Transform and switch the map
- **WHEN** a user rotates or flips the map or switches between Classic and Project
- **THEN** each physical Line retains its number on the wall and in project badges, task rows, selection details, and pending edits

### Requirement: Reservations and current usage are distinct

Project rows SHALL show clickable physical Line badges for their current tasks. Project layout SHALL additionally show saved reservations in a separately labeled group and visibly identify current usage of Shared overflow. Classic SHALL show current placements without labeling saved reservations as current project ownership. Empty groups SHALL be identifiable as empty. Covers AC2.

#### Scenario: Reserved Lines and overflow differ
- **WHEN** a project reserves Lines 2 and 8, has a task on Line 8, and another task uses unreserved Line 11
- **THEN** Project shows reserved badges 2 and 8 and in-use badges 8 and 11, with 11 identified as Shared
- **AND** Classic shows in-use badges for its actual current placements and no reserved group

#### Scenario: Classic task differs from saved owner
- **WHEN** a Classic task occupies a Line saved for another project
- **THEN** that Line's current project association follows the task, and saved ownership does not masquerade as current usage

### Requirement: Shared pool identification

In Project layout, the Shared pool SHALL identify unreserved physical Lines with clickable badges, distinguish available Lines from occupied Lines, and identify an occupied Line's task and project. Project tasks using Shared SHALL remain associated with their own project. Covers AC2–AC3.

#### Scenario: Shared occupancy
- **WHEN** unreserved Line 11 hosts a Notification Service task and unreserved Line 12 is idle
- **THEN** Shared shows Line 11 in use with its task/project identity and Line 12 available
- **AND** Notification Service also shows its usage of Line 11

### Requirement: Task placement labels

Each task row SHALL show a clickable badge for its current physical Line or the text "Waiting for a Line" when it has no placement. Refreshes SHALL update this identification when a task moves, waits, or receives a Line. Covers AC3 and AC5.

#### Scenario: Waiting and placed tasks
- **WHEN** one task occupies Line 8 and another has no eligible Line
- **THEN** their rows show Line 8 and "Waiting for a Line" respectively
- **AND** selecting the waiting task clears any stale Line selection

### Requirement: Local selection connects all views

Clicking a numbered badge SHALL select its physical Line on the wall. Selecting a Line SHALL highlight its occupying task and associated project rows; Project SHALL also highlight its saved reservation owner or Shared pool. Classic association SHALL follow current usage. Modifier selection with Ctrl, Command, or Shift SHALL support multiple Lines and highlight all their associations. Selection and keyboard activation SHALL remain local and SHALL NOT mark Codex tasks read, change assignments, or send physical light requests. This retains the existing map's local selection boundary. Covers AC3 and AC5.

#### Scenario: Badge and map selection agree
- **WHEN** the user clicks a project or task badge for Line 8, or selects Line 8 on the wall
- **THEN** the wall, matching badges, its task, and applicable project rows highlight consistently
- **AND** no write request results from selection

#### Scenario: Selection survives normal polling
- **WHEN** the page refreshes an unchanged state while a numbered badge has keyboard focus
- **THEN** focus and selection remain usable
- **AND** a subsequent placement change updates the selected Line's task/project associations without retaining stale highlights

### Requirement: Inspector identifies selected numbers

The context card SHALL identify a single selected physical Line and name its action "Locate Line N". For multiple selections it SHALL list the actual selected numbers and disable the single-Line Locate action. Reservation editing for the selected Lines, a Reserved for select applied on change and Swap halves, SHALL be offered only while Project layout is active and SHALL keep using the existing assignment request and pending-edit rules. Covers AC4 and issue #135 decision 4.

#### Scenario: Single and multiple selections
- **WHEN** Line 8 is selected
- **THEN** the inspector identifies Line 8 and says "Locate Line 8"
- **WHEN** Lines 2, 8, and 11 are selected together
- **THEN** the inspector lists 2, 8, and 11, and Locate is disabled

#### Scenario: Reservation controls follow the layout
- **WHEN** a Line is selected in Classic layout
- **THEN** no reservation select or Swap halves control is shown
- **WHEN** the layout is Project
- **THEN** those controls appear and choosing a project in Reserved for sends the existing assignment request for the selected Lines

### Requirement: Pending edits identify their destination

Pending reservation edits SHALL identify each physical Line and its destination project or Shared pool. Pending half swaps SHALL identify the Line. Pending task project overrides SHALL identify the task, its currently occupied Line when available, and the destination project or return to Codex assignment. A waiting task SHALL NOT receive an invented Line number. Pending edits SHALL remain pending until the existing bridge rules apply them. Covers AC4–AC5.

#### Scenario: Reservation and task edits wait for a comet
- **WHEN** a pending reservation moves Line 8 to Notification Service
- **THEN** the page reports "Line 8 → Notification Service"
- **WHEN** a pending project override changes the task currently on Line 11 to Daily Trader
- **THEN** the page identifies Line 11, the task, and Daily Trader without claiming a future placement

### Requirement: Locate remains explicit

Only an explicit Locate action SHALL request physical highlighting. The existing action SHALL highlight one selected Line for one second, restore its display, wait for an active comet, use 10% brightness in Quiet, and remain disabled in Free. Selection SHALL preserve modes, assignments, animation timing, scene preferences, unread state, and task state. This requirement retains the bridge guide's existing Locate and selection contract. Covers AC5.

#### Scenario: Select without locating
- **WHEN** the user selects or highlights a number in any mode
- **THEN** no physical highlighting or task-state change occurs
- **WHEN** the user explicitly locates one selected Line in Work or Quiet
- **THEN** the existing Locate behavior applies to that physical Line
- **AND** Free prevents the Locate action

### Requirement: Readable crystal numerals clear neighbouring Lines

The map SHALL use neutral luminous numerals with a crisp readable core, restrained spill, a text height of at least 11 screen pixels and a click envelope of at least 24 by 24 pixels. At the supported 1440, 800 and 390 pixel viewport widths, every rotation and flip SHALL keep label bounds inside the canvas and clear neighbouring final crystal bodies, active selection bounds, connectors and other visible labels. Show-all and simultaneous selections/highlights SHALL preserve this clearance. Physical numbers SHALL remain unchanged and decorative layers SHALL NOT intercept selection. Covers issue #26 AC1, AC2 and AC5.

#### Scenario: Compact transformed wall
- **WHEN** the actual arrangement is rotated or flipped at a supported viewport width with all numbers shown
- **THEN** every numeral remains legible, inside the canvas and clear of neighbouring crystal and ring bounds, including the original compact 90 and 270 degree cases
- **AND** raw clicks on all displayed numbers select their same physical Lines without horizontal page overflow

#### Scenario: Modes preserve legibility
- **WHEN** Work, Quiet, Free or reduced motion changes the wall appearance
- **THEN** the numeral core remains readable and neutral rather than adopting its task's status color, while focus, selected and pending states remain distinguishable

### Requirement: Numeral visibility combines independent reasons

A Line's numeral SHALL be visible when that Line is selected, highlighted, hovered or keyboard-focused. Removing one reason SHALL NOT hide a numeral while another remains. Otherwise the numeral SHALL be hidden unless show-all is enabled. Multiple selected Lines SHALL show their numbers together, and touch selection SHALL retain the numeral without requiring hover. Visibility changes SHALL keep label positions and physical IDs stable. Accessible Line names SHALL retain the physical number when decorative numerals are hidden. Covers AC3 and AC4.

#### Scenario: Hover leaves a selected Line
- **WHEN** a selected or focused Line is hovered and the pointer leaves it
- **THEN** its numeral remains visible until the other visibility reasons also end

#### Scenario: Touch and multiple selection
- **WHEN** touch selects a Line or Ctrl, Command or Shift adds another Line to selection
- **THEN** the selected numbers remain visible with their existing project, task and inspector associations

### Requirement: Show-all is a passive local preference

The map SHALL provide a browser-local show-all preference that defaults off and survives reloads in that browser. Hover, focus, selection, highlighting and show-all SHALL issue no assignment, unread, Locate or light request and SHALL leave task and scene state unchanged. The existing explicit Locate action SHALL remain the only path to physical highlighting. Covers AC4 and AC6.

#### Scenario: Show-all persists without a write
- **WHEN** the user enables show-all and reloads the page
- **THEN** every physical Line's numeral is visible with its stable identity, and no bridge or device mutation was needed to save the display preference
