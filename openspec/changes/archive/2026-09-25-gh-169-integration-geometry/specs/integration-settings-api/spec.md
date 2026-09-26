## ADDED Requirements

### Requirement: Read-only element geometry route
A read-scoped route SHALL return, for any configured device, that device's identity, layout kind and elements in the saved order. Each element SHALL carry its stable element ID, element number, ordered zone IDs and the display points the wall map draws, with the controller's global orientation and Y inversion applied: three points along a Line or the three vertices of a triangle. For the Lines, the response SHALL also carry the connector graph when the saved layout supports it. A device with no saved layout entry SHALL return an explicit empty result; a saved layout without drawable geometry SHALL list its elements with null points. The route SHALL read only the saved layout and one SQLite read transaction, SHALL NOT discover geometry, contact a device, write state or change the extension snapshot's shape, and SHALL carry no address, credential or private path. An unknown device SHALL fail as it does for the extension snapshot. Maps to [issue #169](https://github.com/jimmie-potts/codex-nanoleaf/issues/169) scope and its fake-device and hub-consumer criteria.

#### Scenario: Reading the Lines geometry
- **WHEN** a read-scoped credential reads the geometry route for the Lines with a saved layout and connector geometry
- **THEN** it receives each Line's ID, number, zone pair and three display points in the saved order, plus the connector graph, the database bytes are unchanged and no device is contacted

#### Scenario: Reading the Panels geometry
- **WHEN** a client reads the geometry route for the configured Panels
- **THEN** it receives each triangle's ID, number, panel zone and three vertices in the saved order, with no connector graph

#### Scenario: Device without a saved layout
- **WHEN** a client reads the geometry route for a configured device that has no saved layout entry
- **THEN** it receives the device identity with a null kind, no elements and no connectors

#### Scenario: Unknown device
- **WHEN** a client reads the geometry route naming a device that is not configured
- **THEN** the request fails with the same failure code the extension snapshot returns for that device
