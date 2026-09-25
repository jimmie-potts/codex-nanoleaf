## ADDED Requirements

### Requirement: Read-only extension for other devices
For a configured device other than the original Lines, the extension SHALL be read-only. Its snapshot SHALL keep the extension's exact key set, carry that device's identity, configuration revision, mode and discovered scenes, list no elements, pending wall edit or requests, and mark every configuration operation unsupported. Extension commands for that device, including `animation.play`, SHALL fail with `unsupported-capability` before any reservation or effect. Receipt and cancel lookups under that device SHALL return `request-expired`, and its animation discovery route SHALL return `unsupported-capability`. Shared configuration, element assignment and animations SHALL stay with the original Lines ledger. This requirement maps to [issue #113](https://github.com/jimmie-potts/codex-nanoleaf/issues/113) scope 1.

#### Scenario: Reading the Panels extension snapshot
- **WHEN** the worker has observed the Panels' saved scenes and a client reads the extension snapshot for the Panels
- **THEN** it returns the Panels' identity, revision, mode and named scenes, no elements, and unsupported configuration operations, without contacting either device

#### Scenario: Extension command for the Panels
- **WHEN** a client sends `project.color` or `animation.play` to the extension naming the Panels
- **THEN** the request fails with `unsupported-capability`, no request identity is consumed, and neither device receives a write
