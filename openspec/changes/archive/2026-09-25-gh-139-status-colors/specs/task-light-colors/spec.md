## ADDED Requirements

### Requirement: One stored task-light palette

The installation SHALL keep one palette of five roles in private SQLite: Base, Working, Question, Blocked and Unread. The defaults SHALL be Base `#0A1866`, Working `#00FF00`, Question `#FFFF00`, Blocked `#FF0000` and Unread `#9B30FF`. A role the operator has not changed SHALL use its default, so an upgraded installation starts with these defaults. Chosen colors SHALL survive worker, map and service restarts. Reset colors SHALL restore all five defaults and change nothing else. The same palette SHALL apply to every registered device. Upgrading SHALL keep project colors, reservations, halves, coverage, orientation, layout, mode, scene selection and brightness. Covers issue #139 AC1 and AC11.

#### Scenario: Upgrade adopts the defaults
- **WHEN** an installation with saved project colors, reservations, map settings, mode and scene opens with this version
- **THEN** those settings are unchanged and the effective palette is the default palette

#### Scenario: Choices survive a restart
- **WHEN** the operator sets Unread to magenta and restarts the worker and the map
- **THEN** the effective palette still has magenta Unread and the other roles' current colors

#### Scenario: Reset restores defaults only
- **WHEN** the operator resets colors after changing several roles and a project color
- **THEN** all five roles return to their defaults and the project color is unchanged

### Requirement: Work mode uses the palette

While task indicators show in Work, unused Lines and Lines holding a read or interrupted task SHALL be steady in the Base color. A working, question or blocked task's Line SHALL pulse between 20% and 100% of its chosen color every 2 seconds, and its first pulse after a status change SHALL radiate outward in that color. An unread task SHALL pulse in the Unread color. A completion comet SHALL keep its white head and SHALL fade its tail into the Unread color. After a wave or comet passes, other Lines SHALL return to their own status color or the Base color. Task indicators SHALL use 30% overall brightness. When the last indicator and active comet clear, the remembered scene SHALL return. Covers issue #139 AC2 and AC7.

#### Scenario: Default palette on the wall
- **WHEN** one Line holds an unread task, one holds a read task and the rest are unused
- **THEN** the unread Line pulses in violet, the read and unused Lines are steady dim blue, and a comet from the unread Line has a white head and a violet tail

#### Scenario: Chosen status colors
- **WHEN** Working is set to cyan and a task starts working
- **THEN** its outward wave and its pulse use cyan, and after the wave passes the other Lines return to their own colors

#### Scenario: Base set to Off
- **WHEN** Base is black and one task is blocked
- **THEN** unused Lines receive black frames while the blocked Line pulses red, and when that task clears the remembered scene is selected again

### Requirement: Alert priority follows status, not color

When outward waves or comets overlap, blocked SHALL take priority over question, question over working, and working over unread, whatever colors those statuses use. Red and yellow task Lines, meaning blocked and question Lines in their chosen colors, SHALL remain visible while a comet passes, and blocked and question waves SHALL take precedence over the comet where they pass. Covers issue #139 AC5.

#### Scenario: Swapped hues keep priority
- **WHEN** Blocked is violet, Unread is red, and a blocked wave overlaps a working wave and an unread Line
- **THEN** the overlapping Lines show the violet blocked wave, and a comet passing the blocked Line leaves it violet

### Requirement: Quiet and Free presentation

Quiet SHALL show each assigned Line steadily in its status color, and unused Lines in the Base color, at 10% brightness without pulses, outward waves or comets. Free SHALL send no task colors; its handoff and scene behavior are unchanged. Covers issue #139 AC3.

#### Scenario: Quiet steady colors
- **WHEN** Quiet shows a working task and an unread task with Working set to cyan
- **THEN** the working Line is steady cyan, the unread Line is steady in the Unread color, unused Lines are steady Base, and brightness is 10%

#### Scenario: Free unchanged
- **WHEN** the operator chooses Free after changing the palette
- **THEN** the bridge restores the remembered scene once and sends no palette colors

### Requirement: Project layout halves use the Base color

In Project layout, the status half of a reserved Line without a task and every half of an empty Shared Line SHALL use the Base color while any indicator remains. Project halves SHALL keep their project colors. Under Both halves coverage, waves and comets SHALL cover the project half and return to its project color; under Status half only, the project half SHALL stay steady. Covers issue #139 AC4.

#### Scenario: Reserved and Shared Lines
- **WHEN** Project layout shows a reserved Line without a task and an empty Shared Line while another task works
- **THEN** the reserved Line shows its project color on its project half and Base on its status half, and the Shared Line is Base on both halves

#### Scenario: Both coverage settings
- **WHEN** a working wave passes a reserved Line under Both halves and then under Status half only
- **THEN** the wave covers the project half and returns it to the project color in the first case, and the project half stays steady in the second

### Requirement: Palette changes preserve animation state

A palette change SHALL reach the lights within about two seconds through the existing worker. It SHALL NOT restart pulse epochs, replay outward waves or comets, move tasks between Lines, release comet source reservations, or change mode, scene selection or brightness. The worker SHALL remain the only light writer for each device. Covers issue #139 AC6.

#### Scenario: Change mid-pulse and mid-comet
- **WHEN** Unread is changed while a working task pulses and a comet plays
- **THEN** the next frames use the new color, the working task keeps its pulse epoch, the comet keeps its source and start time, and no task changes Line

### Requirement: Palette writes are validated and local

The wall map SHALL change the palette only through the existing `/api/settings` write, which requires the map's exact host, origin and request token. A request SHALL set one to five roles to `#rrggbb` colors or reset the palette to its defaults. An unknown role, a malformed color or a missing token SHALL be rejected with nothing applied. `/api/state` SHALL report the effective palette for all five roles. The Nanoleaf token SHALL never reach the browser. The integration settings API, CLI, controller API and MCP SHALL offer no palette operation. Covers issue #139 AC10.

#### Scenario: Invalid palette request
- **WHEN** one request sets Unread to a valid color and Base to `#12345`, or names a role `comet`
- **THEN** the request is rejected and neither role changes

#### Scenario: Missing token
- **WHEN** a palette request lacks the request token or comes from another origin
- **THEN** it is rejected and the palette is unchanged

### Requirement: Unchanged white and fallback colors

The completion comet head and the Locate flash SHALL stay white. Before any scene has been remembered, or after the remembered scene was deleted, the idle fallback SHALL stay steady blue `#193CFF` whatever the Base color is. Covers issue #139's unchanged behavior.

#### Scenario: No remembered scene
- **WHEN** the last indicator clears with no remembered scene and Base set to black
- **THEN** the bridge draws the steady blue fallback

### Requirement: Map shows the effective colors

The wall artwork, the legend and the Project halves sample SHALL use the effective palette, with unused Lines drawn in the Base color and unread Lines in the Unread color. Status labels and badges SHALL stay readable against the page whatever colors are chosen. The Colors group SHALL warn, without blocking saving, when two roles are too similar to tell apart, meaning a CIE76 color difference below 20, and name those roles. Covers issue #139 AC8 and AC9.

#### Scenario: Custom palette on the map
- **WHEN** Unread is magenta and Base is black
- **THEN** unread Lines and the Unread legend dot are magenta, unused Lines are black, and the Unread and Idle status labels remain readable

#### Scenario: Similar-color warning
- **WHEN** Unread is set to the Base color
- **THEN** the Colors group warns that Unread and Base look alike, and the warning clears when Unread is changed back
