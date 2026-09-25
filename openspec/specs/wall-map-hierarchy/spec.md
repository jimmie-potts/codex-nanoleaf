# wall-map-hierarchy Specification

## Purpose
Keep the wall map's default screen focused on the wall, the current mode, live status, alerts and the selected item, with secondary controls and repeated explanations available without crowding that view.

## Requirements

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

### Requirement: Secondary controls live under one labelled Options menu

Layout (Classic and Project), animation coverage while Project layout is active, Show all numbers, Rotate, Flip H, Flip V, Replay assembly, Play on opening, Play on view entry and the task-light Colors SHALL sit under one control labelled Options above the wall, in groups labelled Layout, Numbers, Orientation, Assembly and Colors. The Colors group SHALL offer a choice for Base, Working, Question, Blocked and Unread, each with its suggested swatches and a custom color, plus Reset colors and the similar-color warning. The menu SHALL open and close by pointer and keyboard, SHALL close on Escape and return focus to its control, and SHALL close on a pointer press outside it. Each control SHALL keep its identity, accessible name, pressed or checked state, saved preference and current behavior, including the browser-local number and playback preferences, the saved orientation and the saved layout. Opening or closing the menu or the Colors group and toggling the number display or playback preferences SHALL send no request other than state polls; layout, coverage, orientation and color changes SHALL send only the existing settings request and no device command. Covers issue #78 AC2, issue #135 decision 2 and issue #139 AC1.

#### Scenario: Keyboard journey through the menu
- **WHEN** a keyboard user opens Options, moves through Layout, Show all numbers, the orientation buttons, Replay assembly and the playback checkboxes, toggles a preference and presses Escape
- **THEN** each control is reachable in order with its accessible name, the toggled preference persists in this browser after the menu closes and reopens, focus returns to the Options control, and no write request was sent

#### Scenario: Orientation from the menu
- **WHEN** the user rotates the map from the Options menu
- **THEN** the map rotates through the existing settings request, the menu stays open, keyboard focus stays on Rotate through polling, and no other request is sent

#### Scenario: Layout from the menu
- **WHEN** the user chooses Project in the Options Layout group and later Classic
- **THEN** each choice sends one settings request, Coverage appears in the group only while Project is active, and the saved layout survives a reload

#### Scenario: Colors from the menu
- **WHEN** the user opens the Colors group, picks a swatch for Unread, sets a custom Base color and then chooses Reset colors
- **THEN** opening the group sends no request, each choice sends one settings request, the pressed swatch and custom value follow the saved palette through polling and a reload, and Reset colors restores the five defaults

### Requirement: Counts and hints have one primary location

The Line total SHALL appear only in the wall heading, the task total only in the Tasks heading, and blocked and question alerts in the readout, while the task card keeps its status, waiting and shown counts on short lines beside its full-list control. The selection instruction, including the modifier for selecting several Lines, SHALL appear only in the context card; the wall heading and the Projects heading SHALL carry no repeated hint. The footer SHALL keep the read-ownership note. Removed repetitions SHALL leave every control labelled. Covers AC3 and AC4.

#### Scenario: One home for each count
- **WHEN** 72 tasks with 2 blocked and 3 question are shown on 15 Lines
- **THEN** the wall heading says 15 Lines, the Tasks heading says 72, the readout says 2 blocked and 3 question without a Line or task total, and the task card shows the status breakdown, the waiting count and the number shown

#### Scenario: Lists from #76 and #77 fit
- **WHEN** many long-titled tasks and long project names are shown and a task is selected at 390 or 1440 pixels
- **THEN** the selected task, its details and, in Project layout, its reservation select remain usable without horizontal overflow, and the compact grid keeps its two desktop columns

### Requirement: One context card with layout-conditional editing

The inspector SHALL show one context card for the current selection. It SHALL name the selected Line, list several selected Lines, or say that a focused task is waiting for a Line; show the task's title, status, project or "No project", elapsed time and Open in Codex link when it qualifies; and offer Locate, disabled for more than one Line and in Free. The task's title and project SHALL appear once in the inspector outside the task tiles. In Classic layout no reservation or half-swap control SHALL be visible. In Project layout the card SHALL show a Reserved for select above the task, applied on change to every selected Line through the existing assignment request and pending-edit rules, showing a disabled "Several reservations" choice when the selected Lines differ, and Swap halves. The map SHALL NOT offer a per-task project override; that operation remains available to the machine API. Escape SHALL close an open Options menu first and otherwise clear the selection; a click on empty wall canvas SHALL clear the selection; both return focus to the wall heading. The Locate explanation SHALL appear only in Free. Selection, opening the card and switching layout SHALL send no request beyond the existing settings request for a layout change. Covers issue #135 decisions 3 to 6 as revised on 2026-09-24.

#### Scenario: Classic selection
- **WHEN** a Line with a task is selected in Classic layout
- **THEN** the card names the Line, shows the task once with its status, project and elapsed time, offers an enabled Locate and no reservation, half-swap, override or Locate explanation

#### Scenario: Project layout reservation
- **WHEN** Project layout is active and a Line is selected
- **THEN** the card shows Reserved for with the Line's project or Shared pool and Swap halves, choosing another project sends the existing assignment request for the selected Lines, a rejected choice returns to the saved value after focus leaves, and no task override is shown

#### Scenario: Waiting task and several Lines
- **WHEN** a waiting task is chosen from the list, or several Lines are selected
- **THEN** the card says the task is waiting for a Line with its details and no Line actions, or lists the Line numbers with Locate disabled, asks for one Line to inspect a task, and in Project layout shows Several reservations when their reservations differ

#### Scenario: Clearing and Locate hint
- **WHEN** the user presses Escape with a selection, presses Escape while Options is open, clicks empty canvas, or switches to Free
- **THEN** the selection clears with focus on the wall heading, an open Options menu closes first and the selection stays until the next Escape, and the Locate explanation is shown only while Free disables Locate
