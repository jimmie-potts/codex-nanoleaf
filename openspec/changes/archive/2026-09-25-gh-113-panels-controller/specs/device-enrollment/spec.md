## MODIFIED Requirements

### Requirement: Operator guidance without restarts
Enrollment SHALL tell the operator how to activate the device and that no user service needs a restart, because hooks, the worker and the map read the registry when they need it. It SHALL also state that the controller and MCP reach the device only after `controller-configure` adds it ([#113](https://github.com/jimmie-potts/codex-nanoleaf/issues/113)). Listener configuration, trusted hooks, selected modes, reservations and pulse and comet epochs SHALL be preserved. Covers #45 AC5.

#### Scenario: Enrollment output
- **WHEN** enrollment succeeds
- **THEN** its output names the activation command for the new id and states that no service restart is needed and how to add the device to the controller, and the listener ports in the configuration are unchanged
