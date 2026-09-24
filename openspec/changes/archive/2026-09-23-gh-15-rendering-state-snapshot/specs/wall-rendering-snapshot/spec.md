## Purpose

Provides local display clients with the latest rendering output accepted by the Nanoleaf worker, so they can reproduce bridge-controlled effects without scheduling or guessing device output.

## ADDED Requirements

### Requirement: Latest accepted rendering output

The loopback wall-map server SHALL provide a versioned rendering snapshot at `GET /api/rendering` for the worker's latest successful bridge-controlled output. The snapshot SHALL identify each physical Line and its zone IDs, preserve the controller's encoded frames and transition durations, and report the loop setting, mode, effective brightness, and animation epoch. It SHALL identify the worker-send acceptance time separately from the animation epoch. It SHALL NOT include credentials or claim optical verification.

#### Scenario: Pulse or completion output was accepted
- **WHEN** the worker successfully sends a pulse or completion effect and its brightness update
- **THEN** `GET /api/rendering` includes the exact accepted frame payload, zone mapping, loop setting, effective brightness, animation epoch, and send acceptance time

#### Scenario: No accepted bridge output is available
- **WHEN** no successful worker rendering receipt exists or output is controlled by Free mode or an unreadable external scene
- **THEN** the response identifies current output as unknown or externally controlled and does not invent frames from task status

### Requirement: Compact output outcome

The rendering snapshot SHALL distinguish pending worker updates, the latest successful output, and failed or uncertain worker updates. A failure SHALL leave the prior successful receipt identifiable as prior output; it SHALL NOT be presented as the failed update's accepted output. The snapshot MAY report the latest successful receipt alongside a pending or failed outcome.

#### Scenario: Worker update is pending
- **WHEN** task or mode changes are queued for the worker
- **THEN** the response reports pending while retaining any prior successful receipt separately

#### Scenario: Worker update fails
- **WHEN** a controller request in the worker's output pass fails
- **THEN** the response reports a failed or uncertain outcome and preserves only the last fully successful receipt

### Requirement: Passive and restart-safe reads

Reading rendering state SHALL use a read-only database connection and SHALL NOT refresh Codex metadata, acquire device geometry, contact the controller, start a worker, write to the device, advance task or completion effects, reserve sources, clear unread state, change assignments or preferences, or schedule a replay. The latest successful receipt SHALL survive wall-map and worker process restarts. Receipt storage SHALL use existing private Linux state and SHALL not reset existing task, scene, or project data.

#### Scenario: Repeated or restarted reader
- **WHEN** clients poll repeatedly, reconnect, or restart the wall-map server
- **THEN** reads return the current receipt and outcome without changing worker state or replaying an expired effect

#### Scenario: Read route has no write action
- **WHEN** a client submits preview data to `POST /api/rendering`
- **THEN** the server rejects the request and retains the latest worker receipt unchanged

### Requirement: Existing local-server boundary

Rendering state SHALL use the existing loopback map server, preserve its Host and no-store protections, and read SQLite without refreshing metadata or contacting the controller. It SHALL NOT expose Nanoleaf credentials.

#### Scenario: Local read
- **WHEN** a local client reads `/api/rendering`
- **THEN** it receives rendering data without credentials and the response is not cached

#### Scenario: Untrusted host
- **WHEN** a request has an invalid Host header
- **THEN** the server rejects the request and reveals no rendering or private state
