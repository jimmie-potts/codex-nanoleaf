## ADDED Requirements

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
