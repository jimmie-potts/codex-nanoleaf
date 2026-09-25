## MODIFIED Requirements

### Requirement: Per-device modes and scene restoration
Each device SHALL persist its own Work, Quiet and Free selection, applied revision and error. Each device SHALL restore its own latest saved scene and brightness across takeover, idle, Quiet, Free and recoverable failure. Quiet SHALL use the steady 10 percent policy, and Work SHALL keep its brightness policy. A change to one device SHALL NOT clear the other device's effects, pending edits, mode or restoration state. After a successful Free handoff, the device SHALL receive no further requests except the single write of an explicit native power, brightness, scene or animation command on the original Lines device; Free SHALL NOT poll or send task lighting. Display-cache clears and previews SHALL affect only their target device. `setup --reset` and shared-source switching SHALL state that they reset every device, and shared-source switching SHALL preserve bound placements on every device. Covers AC3 and [issue #92](https://github.com/jimmie-potts/codex-nanoleaf/issues/92).

#### Scenario: Mixed modes
- **WHEN** Lines is in Work and Panels is switched to Free
- **THEN** Panels restores its own saved scene once and receives no later requests, while Lines keeps rendering tasks and its comet and pending edits

#### Scenario: Targeted cache clear
- **WHEN** the operator refreshes the Panels device
- **THEN** only the Panels display cache is cleared, and the Lines worker sends nothing because of it
