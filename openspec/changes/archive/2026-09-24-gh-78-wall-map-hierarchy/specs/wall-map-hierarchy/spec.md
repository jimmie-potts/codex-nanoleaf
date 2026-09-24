## Purpose

Keep the wall map's default screen focused on the wall, the current mode, live status, alerts and the selected item, with secondary controls and repeated explanations available without crowding that view.

## ADDED Requirements

### Requirement: The default screen leads with the wall and live status

At the supported 390, 800 and 1440 pixel widths, with dense or empty data, the wall SHALL be the dominant element: its heading SHALL take one row above the wall, the wall SHALL span at least 45 percent of the viewport width and at least 300 pixels of height, and the page SHALL NOT overflow horizontally. The mode controls, the mode note, the connection state, the pending-edit banner, alert counts and error notices SHALL remain visible without opening any menu. Work, Quiet, Free, reduced motion, the empty state, the disconnected state and pending edits SHALL remain visually distinguishable. Covers issue #78 AC1 and AC5.

#### Scenario: Dense and empty data at every width
- **WHEN** 72 tasks and 20 current projects, or no tasks and no projects, are shown at 390, 800 and 1440 pixels
- **THEN** the wall keeps its single-row heading and dominant size, nothing overflows horizontally, and the readout, mode controls and connection state are visible on the first screen

#### Scenario: Alerts stay outside the menu
- **WHEN** a snapshot carries a pending edit, blocked or question tasks, or the connection fails
- **THEN** the pending banner beside the wall, the readout's pending flag and alert counts, and the disconnected connection state are visible with the Options menu closed

### Requirement: Secondary controls live under one labelled Options menu

Show all numbers, Rotate, Flip H, Flip V, Replay assembly, Play on opening and Play on view entry SHALL sit under one control labelled Options above the wall, in groups labelled Numbers, Orientation and Assembly. The menu SHALL open and close by pointer and keyboard, SHALL close on Escape and return focus to its control, and SHALL close on a pointer press outside it. Each control SHALL keep its identity, accessible name, pressed or checked state, saved preference and current behavior, including the browser-local number and playback preferences and the saved orientation. Opening or closing the menu and toggling the number display or playback preferences SHALL send no request other than state polls; orientation changes SHALL send only the existing settings request and no device command. Covers AC2.

#### Scenario: Keyboard journey through the menu
- **WHEN** a keyboard user opens Options, moves through Show all numbers, the orientation buttons, Replay assembly and the playback checkboxes, toggles a preference and presses Escape
- **THEN** each control is reachable in order with its accessible name, the toggled preference persists in this browser after the menu closes and reopens, focus returns to the Options control, and no write request was sent

#### Scenario: Orientation from the menu
- **WHEN** the user rotates the map from the Options menu
- **THEN** the map rotates through the existing settings request, the menu stays open, keyboard focus stays on Rotate through polling, and no other request is sent

### Requirement: Counts and hints have one primary location

The Line total SHALL appear only in the wall heading, the task total only in the Tasks heading, and blocked and question alerts in the readout, while the task card keeps its status, waiting and shown counts on short lines beside its full-list control. The selection instruction, including the modifier for selecting several Lines, SHALL appear only in the selection card; the wall heading and the Projects heading SHALL carry no repeated hint. The footer SHALL keep the read-ownership note. Removed repetitions SHALL leave every control labelled. Covers AC3 and AC4.

#### Scenario: One home for each count
- **WHEN** 72 tasks with 2 blocked and 3 question are shown on 15 Lines
- **THEN** the wall heading says 15 Lines, the Tasks heading says 72, the readout says 2 blocked and 3 question without a Line or task total, and the task card shows the status breakdown, the waiting count and the number shown

#### Scenario: Lists from #76 and #77 fit
- **WHEN** many long-titled tasks and long project names are shown and a task is selected at 390 or 1440 pixels
- **THEN** the selected task, its details and its project override remain usable without horizontal overflow, and the compact grid keeps its two desktop columns
