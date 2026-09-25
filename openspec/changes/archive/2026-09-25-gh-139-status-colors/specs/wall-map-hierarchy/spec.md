## MODIFIED Requirements

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
