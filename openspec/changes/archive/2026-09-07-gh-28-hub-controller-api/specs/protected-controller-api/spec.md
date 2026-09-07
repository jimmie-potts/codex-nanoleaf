## Purpose

Provide authenticated local machine status and mode control for Nanoleaf while preserving its Windows worker, private state and existing task animation behavior.

## ADDED Requirements

### Requirement: Explicit local identity and private status

The controller SHALL expose contract API `1.0` snapshots containing operator-configured neutral identity, capabilities, desired mode, bounded pending supported commands, outcome and freshness evidence. It SHALL reject unsupported wire versions and unknown fields and SHALL NOT derive public identity or labels from conversation titles, project names or private paths. Missing observation evidence SHALL remain unknown independently of service health. This requirement maps to [issue #28](https://github.com/jimmie-potts/codex-nanoleaf/issues/28), the identity/status criterion.

#### Scenario: Status has no observed device state

- **WHEN** an authorized client reads a configured controller that has no recorded device observation
- **THEN** the response includes configured identity and saved mode, reports observation as unknown, and excludes credentials, destinations, titles and paths

#### Scenario: Snapshot time advances without observation

- **WHEN** a client takes a later snapshot without a new observation
- **THEN** only sampling/liveness evidence can advance and device evidence is not made fresh

### Requirement: Separate machine authorization and finite limits

The machine endpoint SHALL be opt-in, bind loopback by default, require its exact configured local Host, and authenticate independently of wall page edit tokens before reads, admission or replay. It SHALL enforce configured target and read/control scopes, validate supplied Origin and Fetch-Metadata, support immediate credential revocation, and enforce advertised finite body, time, concurrency, queue and history limits. This requirement maps to issue #28's authentication/bounds criterion.

#### Scenario: Browser token and hostile origin are rejected

- **WHEN** a request supplies only a wall edit token or supplies a disallowed Origin/Host with a machine credential
- **THEN** the endpoint rejects it before cache lookup, request reservation or any effect

#### Scenario: Revocation blocks historical results

- **WHEN** a credential is revoked and its client repeats a previously successful request or polls the feed
- **THEN** authentication fails before a cached response is returned and unsent work for that credential cannot begin

#### Scenario: A read principal attempts control

- **WHEN** a principal without control scope or without the selected target submits a command
- **THEN** the endpoint rejects it without reserving a request identity or changing desired state

#### Scenario: A resource bound is reached

- **WHEN** a body, request deadline, concurrent request or pending queue limit is exceeded
- **THEN** the endpoint returns a bounded typed error before a new effect, and pre-admission capacity rejection consumes no identity

### Requirement: Supported modes preserve existing ownership

The controller SHALL advertise Work, Quiet and Free as supported modes and power, brightness, media, zones, scenes and preview as unsupported. Accepted mode requests SHALL use existing Windows state coordination and the single Windows light worker. Existing mode brightness, scene restoration, pulse timing, unread behavior, project reservations and WSL forwarding SHALL remain intact. This requirement maps to issue #28's worker-ownership and unavailable-preview criteria; the retained baseline is the [bridge guide](../../../bridge/README.md).

#### Scenario: A client requests Quiet

- **WHEN** an authorized fresh command requests Quiet
- **THEN** the existing worker applies the current Quiet policy and the API does not independently send a light request

#### Scenario: A client requests unsupported brightness or preview

- **WHEN** a client inspects capabilities or requests an unsupported brightness operation
- **THEN** preview is explicitly unavailable and unsupported control is rejected through the shared contract without a new effect

#### Scenario: Installed WSL command dispatch

- **WHEN** an installed WSL controller command is invoked
- **THEN** it forwards to Windows before opening controller state, or fails without state changes when Windows is unavailable

### Requirement: Read-only snapshot and resynchronization

Discovery, snapshot and feed retrieval SHALL cause no state migration, task metadata synchronization, allocation, unread acknowledgment, queue advancement, worker launch or device request. Feed history SHALL be bounded and revisioned in its own epoch namespace. Retained cursors SHALL return later events in order; invalid, expired, foreign-epoch or future cursors SHALL return one current resync. This requirement maps to issue #28's pure-read and bounded replay criteria.

#### Scenario: Repeated reads during an active comet

- **WHEN** authorized clients repeatedly read snapshot and feed while a comet, unread task and deferred wall edit exist
- **THEN** task/effect epochs, reservations, unread records, queue contents and device-write counts remain unchanged

#### Scenario: Feed recovery after history expires

- **WHEN** a client reconnects with a cursor that is no longer retained
- **THEN** it receives one authoritative resync and no commands or expired effects are replayed

### Requirement: Atomic command identity and revision checks

Commands SHALL follow the shared server-issued request epoch/sequence, configuration revision and generation contract. Admission and desired-state changes SHALL commit atomically. Exact duplicates SHALL join the original pending work or return its retained receipt without reexecution; changed bodies SHALL conflict. Expired/foreign request identities and future sequences SHALL reject. Reserved semantic failures SHALL retain their receipts. This requirement maps to issue #28's revisioned admission criterion.

#### Scenario: Concurrent clients use one identity

- **WHEN** two authorized clients submit different bodies with the same advertised request identity
- **THEN** at most one reserves it and the other receives request-conflict without another execution

#### Scenario: Browser changes mode before native admission

- **WHEN** the browser commits a mode change after a native client reads a snapshot
- **THEN** the native stale request cannot overwrite that choice and its reserved semantic rejection is replayable

#### Scenario: A completed request is repeated after cache eviction

- **WHEN** a client repeats an older uncached request sequence or one from an expired epoch
- **THEN** the request is expired and cannot be admitted as new work

### Requirement: Generation-aware execution and honest recovery

The worker SHALL check current generation before each queued side effect and cancel superseded work without a new send. Receipts SHALL distinguish queued, successful transmission, failure, partial effect, uncertainty and cancellation without claiming physical success. Recovery after possible unrecorded transmission SHALL retain uncertainty and SHALL NOT automatically execute the same machine request again. Last successful-send evidence SHALL survive later failures. This requirement maps to issue #28's stale-command and unavailable-worker/recovery criteria.

#### Scenario: Queued mode is superseded

- **WHEN** a newer browser or machine mode decision retires a queued generation
- **THEN** the old request is cancelled before another side effect and existing task epochs are not reset to implement public generation changes

#### Scenario: Worker fails before any attempt

- **WHEN** the worker cannot start or an unsent request exceeds its pending deadline
- **THEN** the receipt reports a bounded failure without claiming transmission and replay does not create another request

#### Scenario: Failure follows a partial send

- **WHEN** one sub-operation transmits and a later sub-operation fails or loses its result
- **THEN** the receipt preserves completed/uncertain operation evidence and cannot claim priorEffects none

#### Scenario: Restart finds an incomplete send attempt

- **WHEN** the owning service restarts after a durable attempt marker but before a committed transport result
- **THEN** it reports uncertainty with possible prior effects, requires explicit new admission for a retry, and preserves task/unread/reservation state

### Requirement: Immutable compatibility and isolated adoption

The controller SHALL consume a verified immutable contract artifact with a recorded version, source revision, release location and SHA-256. Adoption verification SHALL cover the shared fixture corpus and owning HTTP/worker behavior on isolated state. Legacy startup SHALL remain usable with the optional machine dependency absent. Source delivery SHALL NOT activate a personal listener or change installed credentials, hooks or physical devices. This requirement maps to issue #28's dependency, verification and source-only target.

#### Scenario: Artifact bytes are altered

- **WHEN** the archive or a manifest-listed dependency file differs from the pinned artifact
- **THEN** machine activation fails before opening the listener or admitting commands

#### Scenario: Legacy operation without controller dependencies

- **WHEN** machine dependencies are unavailable and the listener is disabled
- **THEN** existing hook/mode/map/worker commands retain their standard-library startup behavior

#### Scenario: Existing state is migrated and reopened

- **WHEN** controller bookkeeping is initialized against an existing isolated bridge database
- **THEN** sessions, task/effect epochs, unread receipts, slots, reservations and saved preferences survive unchanged
