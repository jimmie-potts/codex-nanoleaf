## MODIFIED Requirements

### Requirement: Triangle status display
Whole triangles SHALL show the shared task-light palette's Working, Question, Blocked and Unread colors, with the two-second pulse, one outward status wave and the completion comet. Travel SHALL be calculated within that device's arrangement. Overlapping effects SHALL keep blocked and question alert priority and active comet source reservations. Covers AC10 and issue #139 AC12.

#### Scenario: Wave across triangles
- **WHEN** a triangle's task becomes blocked
- **THEN** the blocked-color wave reaches neighboring triangles before distant ones, and afterward only that triangle pulses in the blocked color

#### Scenario: Comet with alerts
- **WHEN** a comet crosses triangles while another triangle shows a question
- **THEN** the question triangle stays in the question color, and the other triangles show the comet and then return to their state

#### Scenario: Chosen palette on the Panels
- **WHEN** Working is set to cyan and a Panels triangle holds a working task
- **THEN** that triangle pulses cyan, the same color the Lines use for working

### Requirement: Triangle slots and reservations
One triangle SHALL supply one task slot. Project reservations SHALL apply per triangle, and a six-triangle region SHALL be reservable through an ordinary multi-element edit. Project identity SHALL appear through reservations and the map, never through triangle halves. Lines SHALL keep their half behavior. Classic and Project allocation, Shared overflow, waiting tasks and the idle baseline SHALL follow the selected device's existing policies. Covers AC11.

#### Scenario: Six-triangle reservation
- **WHEN** six triangles are reserved for a project in Project layout
- **THEN** that project's tasks use only those triangles or Shared triangles, and other projects never borrow them

#### Scenario: No triangle halves
- **WHEN** Project layout shows a reserved but unused triangle while indications remain
- **THEN** the whole triangle shows the palette's Base color, not a project half
