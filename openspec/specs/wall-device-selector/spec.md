# wall-device-selector Specification

## Purpose
Let the wall map show and edit one registered Nanoleaf device at a time, switching between the original Lines and the NL22 Light Panels, while every existing protection and the Lines presentation stay unchanged. Scope is [issue #44](https://github.com/jimmie-potts/codex-nanoleaf/issues/44).

## Requirements

### Requirement: Device selector and URL persistence

The map SHALL open on the original Lines device. When more than one device is registered, a control labelled Device beside the wall heading SHALL list the registered devices by a readable name and switch the page to the chosen one. The chosen device SHALL be kept in the page URL so that a reload stays on it; the original Lines device needs no URL parameter. With only Lines registered the page SHALL show no selector and SHALL behave as it does today. The registered devices SHALL be read on each state request, so a device enrolled while the map runs appears without a map restart. Covers [#44](https://github.com/jimmie-potts/codex-nanoleaf/issues/44) AC1.

#### Scenario: Open and switch
- **WHEN** the map is opened with Lines and Light Panels registered
- **THEN** it shows the Lines, and choosing Light Panels in the Device control switches the wall, the mode controls, the readout and the inspector to the Panels

#### Scenario: Reload keeps the device
- **WHEN** the page is reloaded after Light Panels were chosen
- **THEN** it opens on the Light Panels again

#### Scenario: Newly enrolled device appears
- **WHEN** a device is enrolled while the map is running
- **THEN** the next state read lists it and the Device control offers it

#### Scenario: Lines only
- **WHEN** only the Lines device is registered
- **THEN** no Device control is shown and the page behaves as before

### Requirement: Device-scoped map API

State reads and the mode, settings, assignment, Locate and eviction actions SHALL accept a registered device, state through a query parameter and actions through a `device` field. Requests naming no device SHALL address the original Lines device, so existing browser and CLI callers behave as before. Requests naming an unregistered device SHALL be rejected without addressing Lines and without changing state; a rejected state read SHALL still name the registered devices. Project colours and task project assignment SHALL stay shared across devices. The protected controller API, the integration settings extension and MCP SHALL stay Lines-only. Covers AC2.

#### Scenario: Untargeted request
- **WHEN** a state read or an action names no device
- **THEN** it addresses the Lines device, whatever the registry order

#### Scenario: Targeted request
- **WHEN** a state read or an action names the Panels
- **THEN** it reads or changes only the Panels' state, mode, layout settings, reservations or Locate

#### Scenario: Unknown device
- **WHEN** a state read or an action names a device that is not registered
- **THEN** it is rejected, nothing changes on any device, and the rejection lists the registered devices

#### Scenario: Shared project colour
- **WHEN** a project colour is changed while the Panels are selected
- **THEN** the Lines show the same colour

### Requirement: Selected device status

The page SHALL show the selected device's mode with the Work, Quiet and Free controls, its pending state and last error in the readout, its reservations and its waiting count. Changing one device's mode SHALL leave the other device's mode and saved scene unchanged. Covers AC3.

#### Scenario: Panels mode
- **WHEN** Quiet is chosen while the Panels are selected
- **THEN** the Panels enter Quiet, the readout follows, and the Lines keep their mode and saved scene

### Requirement: Triangle view

For a Light Panels device the wall SHALL draw one plain triangle per element from the cached geometry, in the reported arrangement, filled with its task's status colour or the Base colour without pulse, wave or comet animation, and numbered in the order the geometry reader returns them. Triangles SHALL support selection, modifier multi-selection, keyboard focus and activation, Project-layout reservation and Shared release through Reserved for, the context card's task information and the explicit Locate. The Coverage and Swap halves controls SHALL be hidden for triangles, and the backend SHALL reject a coverage setting and a half swap for a one-zone element. Lines SHALL keep those controls. Covers AC4.

#### Scenario: Triangles drawn
- **WHEN** the synthetic 18-triangle Panels device is selected
- **THEN** the wall shows 18 numbered triangles whose numbers follow the geometry reader's order, each in its task's status colour or the Base colour, with no running animation

#### Scenario: Reserve and release
- **WHEN** several triangles are selected in Project layout and a project, then Shared pool, is chosen under Reserved for
- **THEN** the existing assignment request addresses the Panels for those triangles, and the reservation is shown and then released

#### Scenario: Rejected split-half settings
- **WHEN** a coverage setting or a half swap is requested for the Panels
- **THEN** the request is rejected and the Panels' settings and reservations are unchanged

#### Scenario: Keyboard selection
- **WHEN** a triangle is focused and Enter is pressed, and Escape is pressed afterwards
- **THEN** the triangle is selected with its task in the context card, and the selection clears with focus on the wall heading

### Requirement: Per-device orientation

Rotate, Flip H and Flip V SHALL apply to the selected device and SHALL be saved per device. Covers AC5.

#### Scenario: Rotate the Panels
- **WHEN** the map is rotated while the Panels are selected
- **THEN** the Panels' saved rotation changes and the Lines' saved rotation does not

### Requirement: Protections hold across devices

Selection, refresh and switching devices SHALL send no request other than state polls and SHALL send no Locate or light effect. Display reads SHALL use cached geometry and SHALL never contact a device. Writes SHALL keep the request-origin and edit-token checks, and no browser response SHALL include a Nanoleaf credential. Switching to the Panels SHALL play no assembly, and the Lines assembly SHALL be unchanged: a page that opens on the Panels plays the opening assembly once when the Lines first appear, as on any first load, and later switches replay nothing. Under reduced motion the triangle view SHALL run no animation, and at the supported 390, 800 and 1440 pixel widths it SHALL show without horizontal overflow. Covers AC6 and AC7.

#### Scenario: Passive switching
- **WHEN** the user switches devices, selects triangles and lets the page poll
- **THEN** only state reads are issued, and no Locate or effect reaches either device

#### Scenario: No device contact
- **WHEN** the Panels' state is read while its address is unreachable
- **THEN** the cached geometry is shown and no request is sent to the device

#### Scenario: Credentials stay private
- **WHEN** state is read for either device
- **THEN** the response contains neither device's credential

#### Scenario: Reduced motion and widths
- **WHEN** reduced motion is requested, or the viewport is 390, 800 or 1440 pixels wide, with the Panels selected
- **THEN** no wall animation runs and the page does not overflow horizontally

#### Scenario: No assembly on the Panels
- **WHEN** the user switches from the Lines to the Panels and back
- **THEN** no assembly plays on the Panels, and the Lines return without replaying the opening assembly
