## MODIFIED Requirements

### Requirement: Fixed status and mode delegation
The tools SHALL expose only pure status and Work/Quiet/Free mode intent through the protected controller API. The host SHALL validate input and output with the released shared contract and SHALL preserve the existing designated worker's ownership. This maps to issue #33 criteria 1 through 4.

#### Scenario: Pure status and exact mode request
- **WHEN** status or discovery is requested
- **THEN** no task state is reserved, advanced or written and no light work is submitted
- **WHEN** a valid mode request is submitted
- **THEN** its request ID and expected revisions are passed unchanged to the fixed controller/device through `mode.set`
- **AND** the controller's valid receipt, including cancelled no-op and unknown observation evidence, is preserved without claiming visible output

#### Scenario: Caller selects an unsupported destination or operation
- **WHEN** tool arguments include a target override, raw URL, file path, unknown field or unsupported operation
- **THEN** validation rejects the call before any effect

### Requirement: Bounded Windows and WSL transport
Direct HTTP hosts on Windows or Linux SHALL call only their configured numeric loopback controller. WSL hosts targeting a legacy Windows installation SHALL retain the bounded Windows Python helper for the same fixed routes. No MCP route SHALL open the bridge database, launch a worker directly, accept arbitrary destinations or expose credentials. This maps to issue #33 criteria 5, 6 and 8.

#### Scenario: Same-machine helper exchange
- **WHEN** a WSL host sends a valid request through the configured Windows runtime and helper
- **THEN** the helper performs one fixed controller HTTP exchange with bounded stdin, stdout, time and concurrency
- **AND** credentials travel through stdin rather than command-line arguments and no proxy or redirect is followed

#### Scenario: Broken or hostile transport
- **WHEN** runtime/configuration is missing or input, response, timing or concurrency exceeds its bound
- **THEN** the call settles with a bounded failure and no database access or automatic retry
- **AND** possible effects after dispatch remain uncertain

#### Scenario: Linux direct HTTP exchange
- **WHEN** the Linux MCP host uses the direct HTTP configuration for its Linux controller
- **THEN** it sends the same authenticated bounded controller requests over numeric loopback without launching a Windows helper


### Requirement: Immutable source qualification and acceptance boundary
The source SHALL pin and verify the released shared package, provide Windows, WSL-to-Windows and fresh Linux client templates and qualify both supported MCP versions with fake-controller protocol tests. Installation and physical acceptance SHALL remain separately authorized in #34 for legacy Windows and #55 for the Linux fresh install. This maps to issue #33 criteria 7 and 8.

#### Scenario: Isolated consumer validation
- **WHEN** the source is installed and tested without sibling repositories, personal credentials or devices
- **THEN** the vendored artifact, installed manifest and shared contract validate and real protocol fixtures cover both routes and qualified versions

#### Scenario: Source handoff
- **WHEN** source checks pass
- **THEN** the handoff reports source revision and test evidence separately from unperformed installed Codex, Windows/WSL deployment and physical-light observations
