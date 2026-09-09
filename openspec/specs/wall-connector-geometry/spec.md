# wall-connector-geometry Specification

## Purpose

Provide exact connector positions and stable Line-end relationships for a wall renderer while preserving existing state, identity, and private controller configuration.

## Requirements

### Requirement: Sanitized connector graph

Wall state SHALL expose an additive version-one connector graph when supported geometry is available. It SHALL preserve existing Line fields, group order, physical numbering, sorted-pair Line IDs, and ordered zone IDs. Co-located connector entries SHALL share one housing with retained source identities. Coordinates SHALL apply controller orientation and display-Y inversion once; browser rotation and flips SHALL remain presentation transforms. The projection SHALL exclude credentials, addresses, local paths, and task metadata. Covers issue #52 AC1, AC4, and AC5.

#### Scenario: Actual arrangement retains identity
- **WHEN** the wall reads the saved fifteen-Line fixture with its configured group ordering
- **THEN** the graph contains the reported connector centers and two distinct ends for each existing Line, with numbering and zone order unchanged
- **AND** global orientation and Y inversion match the existing wall coordinates

#### Scenario: Duplicate housing entries
- **WHEN** two supported connector entries report the same housing position within controller rounding tolerance
- **THEN** the graph uses one housing and retains both source IDs without changing light-zone IDs

#### Scenario: Private input stays private
- **WHEN** configuration and raw controller data contain unrelated private fields
- **THEN** the graph contains only validated drawing fields and the existing request protections still apply

### Requirement: Compatible cache enrichment

The backend SHALL enrich fresh and zone-only caches through its existing authorized layout-read path. It SHALL publish a complete validated cache atomically and preserve unrelated layout fields and application state. A valid cache SHALL require no device request. The drawing path SHALL never send light writes, launch Windows helpers, or create another state owner. Covers issue #52 AC2 and AC6.

#### Scenario: Zone-only cache acquires connector positions
- **WHEN** a legacy cache has valid light-zone positions but lacks connector positions and an authorized layout read succeeds
- **THEN** the backend adds the validated connector cache while retaining its existing zone geometry and all unrelated saved state
- **AND** subsequent reads use the cache without another controller request

#### Scenario: Concurrent readers see complete data
- **WHEN** the backend enriches the cache while state readers are active
- **THEN** each reader observes a complete old or new projection and the saved layout remains valid JSON

#### Scenario: Independent layout writer retains its update
- **WHEN** another process changes shared layout configuration during connector-cache publication
- **THEN** its complete update remains intact and the drawing cache cannot overwrite it

#### Scenario: Cached restart is local
- **WHEN** the wall backend restarts with a valid drawing cache and no embedded connector geometry
- **THEN** it reconstructs the connector projection and any missing Line points without contacting the device

#### Scenario: Rediscovery invalidates old drawing geometry
- **WHEN** the documented layout rediscovery replaces saved layout configuration while retaining physical Line IDs
- **THEN** the backend obtains the current connector positions and orientation instead of reusing the earlier drawing cache

### Requirement: Bounded failure and fallback

Invalid, ambiguous, missing, or unsupported connector geometry SHALL NOT replace the last valid cache or create guessed connections. Without exact geometry, the existing Line projection SHALL remain available with a sanitized connector-availability result. Automatic acquisition SHALL use a bounded attempt budget and delay; repeated state polls SHALL NOT cause continuous device polling in Free mode or after the budget is exhausted. A later permitted attempt SHALL recover when valid data becomes available. Covers issue #52 AC3 and AC4.

#### Scenario: Controller failure preserves the wall
- **WHEN** a connector read fails or yields malformed data
- **THEN** the last valid connector graph and existing Line projection remain unchanged, no partial cache is published, and no private failure text reaches the browser

#### Scenario: Retry budget is exhausted
- **WHEN** the configured bounded acquisition attempts fail and the browser continues polling
- **THEN** no further automatic device request occurs during that server lifetime and the existing wall remains usable

#### Scenario: Unsupported topology
- **WHEN** a layout has unsupported connector shapes, ambiguous end candidates, invalid zone mapping, or incompatible connector faces
- **THEN** the backend reports exact connector geometry unavailable without fabricating a housing or changing Line identities
