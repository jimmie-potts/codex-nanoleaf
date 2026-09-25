# panels-rendering Specification

## Purpose
Read original NL22 Light Panels layouts into one-zone triangle elements and render the bridge's task colors and animations on whole triangles through HTTP custom and static effects. Scope is [issue #43](https://github.com/jimmie-potts/codex-nanoleaf/issues/43).

## Requirements

### Requirement: NL22 geometry
The worker SHALL read a reported NL22 layout into stable one-zone triangle elements. Each element SHALL keep its panel identity, coordinates and orientation. The cached geometry SHALL record which triangles share edges. Non-light modules SHALL be excluded. Malformed, overlapping, disconnected or unsupported geometry SHALL be rejected rather than mapped as Lines. Identities SHALL come from reported geometry, never from a photo. Covers [#43](https://github.com/jimmie-potts/codex-nanoleaf/issues/43) AC8.

#### Scenario: Supported layout
- **WHEN** a Panels device reports triangles and a Rhythm module
- **THEN** each triangle becomes one element whose id is its panel ID and whose position is its reported centroid, the Rhythm module is excluded, and the saved layout keeps coordinates, orientation and edge neighbors

#### Scenario: Unsupported geometry
- **WHEN** the reported layout has a non-triangle light shape, duplicate or non-numeric panel data, overlapping triangles or a disconnected triangle
- **THEN** reading fails with an error, and no layout is saved

### Requirement: NL22 payloads
The worker SHALL generate HTTP custom and static effect payloads for NL22 with one zone per triangle and no Lines-only logical-panel flag. Assumptions about paired Lines zones SHALL stay in the Lines renderer. Both renderers SHALL run under the existing worker program, with one writer per physical device and independently addressed transport. Covers AC9.

#### Scenario: Custom triangle payload
- **WHEN** the Panels instance renders one working task
- **THEN** the payload's zone count equals the triangle count, every triangle has one frame list whose transition times cover the two-second cycle, and `logicalPanelsEnabled` is absent

#### Scenario: Lines payload unchanged
- **WHEN** the Lines instance renders the same task
- **THEN** its payload still lists both zones of each Line with `logicalPanelsEnabled` true

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

### Requirement: Triangle Locate
An explicit Locate SHALL target only the chosen physical triangle, respect that device's Free mode and keep the current completion-source rules. Ordinary selection and read requests SHALL NOT send Locate or effects. Covers AC12.

#### Scenario: Locate one triangle
- **WHEN** Locate is requested for one triangle on Panels in Work
- **THEN** only that triangle flashes white on the Panels device, and the Lines device receives nothing

#### Scenario: Locate in Free
- **WHEN** Panels is in Free
- **THEN** a Panels Locate request is rejected and nothing is sent

### Requirement: Synthetic NL22 fixture
A synthetic, anonymized 18-triangle fixture SHALL exercise the expected three-hexagon topology. It SHALL contain no live IDs, credentials, raw device state, photo or private task data. Reading SHALL support any valid reported triangle count rather than a fixed 18. Existing Lines fixture and payload coverage SHALL remain. Covers AC13.

#### Scenario: Fixture topology
- **WHEN** the fixture layout is read
- **THEN** it yields 18 connected triangles in three hexagons, and a subset of the same fixture with a different valid count also reads successfully
