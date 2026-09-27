## MODIFIED Requirements

### Requirement: Device boundary

Every demo entry point SHALL, before calling any bridge function, refuse outbound socket connections, datagram sends, new processes (the audited process events and the unaudited launcher that multiprocessing's spawn and forkserver use), foreign libraries and symbols loaded through ctypes, on Python 3.14 any foreign call through ctypes, and new subinterpreters, and SHALL route the wall server's light-request seam to a trap. Each refusal SHALL be appended to the run's `device-boundary.jsonl` with its kind, target and time and SHALL NOT include a credential. The wall server SHALL treat a refusal as an unreachable device. (Issue #193: device-request traps fail on attempted physical requests.)

#### Scenario: Attempted physical and service requests
- **WHEN** a guarded process calls the Nanoleaf transport, the worker launcher or a loopback service
- **THEN** each attempt fails as a boundary refusal, is recorded, and the service receives no connection, while an unguarded control process does connect

#### Scenario: A path that bypasses the seam
- **WHEN** a guarded map geometry read uses the default transport
- **THEN** its socket connection is refused and recorded

#### Scenario: Served map without saved geometry
- **WHEN** `layout-unavailable` is served
- **THEN** its startup layout read is recorded as a refused light request, the map reports the unavailable layout and the server keeps serving

#### Scenario: Paths without a socket or process audit event
- **WHEN** a guarded process starts a multiprocessing spawn child, loads a library or looks up a symbol through ctypes, on Python 3.14 calls a foreign function resolved before the boundary, or creates a subinterpreter where Python provides one
- **THEN** each attempt is refused and recorded and the service receives no connection, while an unguarded control process reaches it by each path
