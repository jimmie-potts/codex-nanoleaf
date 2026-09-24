## MODIFIED Requirements

### Requirement: Inspector identifies selected numbers

The context card SHALL identify a single selected physical Line and name its action "Locate Line N". For multiple selections it SHALL list the actual selected numbers and disable the single-Line Locate action. Reservation editing for the selected Lines, the reservation select with its Reserve action and Swap halves, SHALL be offered only while Project layout is active and SHALL keep using the existing assignment request and pending-edit rules. Covers AC4 and issue #135 decision 4.

#### Scenario: Single and multiple selections
- **WHEN** Line 8 is selected
- **THEN** the inspector identifies Line 8 and says "Locate Line 8"
- **WHEN** Lines 2, 8, and 11 are selected together
- **THEN** the inspector lists 2, 8, and 11, and Locate is disabled

#### Scenario: Reservation controls follow the layout
- **WHEN** a Line is selected in Classic layout
- **THEN** no reservation select, Reserve or Swap halves control is shown
- **WHEN** the layout is Project
- **THEN** those controls appear and reserving the Line sends the existing assignment request
