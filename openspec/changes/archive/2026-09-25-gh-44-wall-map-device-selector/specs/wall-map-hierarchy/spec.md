## MODIFIED Requirements

### Requirement: The default screen leads with the wall and live status

At the supported 390, 800 and 1440 pixel widths, with dense or empty data, the wall SHALL be the dominant element: its heading SHALL take one row above the wall, the wall SHALL span at least 45 percent of the viewport width and at least 300 pixels of height, and the page SHALL NOT overflow horizontally. When more than one device is registered, a control labelled Device SHALL sit beside the wall heading in that row and name the selected device. The header SHALL hold only the Mode controls, the live readout and the connection state; layout switching and animation coverage live in the Options menu. The mode controls, the mode note, the connection state, the pending-edit banner, alert counts and error notices SHALL remain visible without opening any menu. Work, Quiet, Free, reduced motion, the empty state, the disconnected state and pending edits SHALL remain visually distinguishable. Covers issue #78 AC1 and AC5, issue #135 decision 1 and issue #44 AC1.

#### Scenario: Dense and empty data at every width
- **WHEN** 72 tasks and 20 current projects, or no tasks and no projects, are shown at 390, 800 and 1440 pixels
- **THEN** the wall keeps its single-row heading and dominant size, nothing overflows horizontally, and the readout, mode controls and connection state are visible on the first screen

#### Scenario: Alerts stay outside the menu
- **WHEN** a snapshot carries a pending edit, blocked or question tasks, or the connection fails
- **THEN** the pending banner beside the wall, the readout's pending flag and alert counts, and the disconnected connection state are visible with the Options menu closed

#### Scenario: Header holds mode only
- **WHEN** the map opens in Classic or Project layout
- **THEN** the header shows Work, Quiet and Free, the readout and the connection pill, and no layout or coverage control

#### Scenario: Device selector beside the heading
- **WHEN** Lines and Light Panels are registered
- **THEN** the Device control sits in the wall heading row, names the selected device, and the header still holds only Mode, the readout and the connection state
