## Purpose

Provide authenticated local machine status and mode control for Nanoleaf for each configured device while preserving that device's designated single worker, OS-local private state and existing task animation behavior.

## Requirements

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

### Requirement: General controls execute through the single worker queue

`power.set`, `brightness.set` and `scene.activate` SHALL be admitted through the same request identity, configuration revision, generation, replay and capacity rules as mode commands, and SHALL execute as one journaled transport write by the target device's single worker. A failed or uncertain write SHALL hold that device exactly as an uncertain mode write does, and neither the worker's automatic retry nor a read SHALL execute the request again; a fresh native request or explicit mode choice authorizes another attempt. An explicit mode command SHALL cancel that device's queued general controls as stale generation before another side effect. This requirement maps to issue #64 AC2 and AC4 and to [issue #113](https://github.com/jimmie-potts/codex-nanoleaf/issues/113) scope 3.

#### Scenario: Identical power requests replay

- **WHEN** a client submits the same `power.set` body twice under one request identity
- **THEN** the second submission joins the pending work or returns the retained receipt, and the device receives at most one write for that request

#### Scenario: Uncertain brightness write is held

- **WHEN** the transport fails after a brightness write may have reached the device
- **THEN** the receipt reports uncertainty with possible prior effects, the worker's automatic retry does not send it again, and a later explicit mode choice can send new work

#### Scenario: Mode command supersedes a queued control

- **WHEN** a browser, CLI or native mode command commits while a general control is queued
- **THEN** the queued control is cancelled with stale generation and is never sent

### Requirement: Brightness and power overrides persist until the next explicit mode command

A `brightness.set` command SHALL be accepted in Work, Quiet and Free and SHALL record a user override that the worker applies to every brightness it writes in the current mode: Work task indicators and comets, Quiet steady colors, the blue fallback, and the remembered scene when it is restored while idle. A `power.set` command SHALL be accepted in all three modes as one write; while desired power is off the worker SHALL send no indicator, restoration or preview writes, and task tracking SHALL continue. The next explicit mode command from any owner, including the same mode, SHALL clear both overrides and reapply that mode's policy: Work indicators at 30% and the remembered scene at its remembered brightness, Quiet at 10%, Free's one-time handoff, and lights on. While the bridge owns the lights in Work or Quiet, overrides SHALL NOT change the remembered scene brightness; a brightness set in Free is an external change, like one made in the Nanoleaf app, and becomes the preference on the next Work or Quiet observation. This requirement maps to issue #64 AC3.

#### Scenario: Work indicators use the override

- **WHEN** brightness 60 is accepted while Work indicators are showing
- **THEN** the device receives brightness 60 at once and later indicator writes in Work use 60 instead of 30

#### Scenario: Quiet idle keeps the override and same-mode Quiet reapplies 10%

- **WHEN** brightness 50 is accepted while Quiet shows the remembered scene, and an explicit Quiet command follows
- **THEN** the scene plays at 50 until that command, after which the worker writes 10% and the remembered brightness is unchanged

#### Scenario: Work idle override is reapplied by a same-mode Work command

- **WHEN** brightness 70 is accepted while Work shows the remembered scene, and an explicit Work command follows
- **THEN** the scene plays at 70 until that command, after which the worker restores the remembered brightness without re-selecting the scene

#### Scenario: Power off suppresses indicator writes until a mode command

- **WHEN** power off is accepted in Work and a task status then changes
- **THEN** the device receives one power-off write and no indicator writes, task placements and epochs continue, and the next explicit mode command renders the current indicators with lights on

#### Scenario: Brightness set in Free becomes the preference

- **WHEN** brightness 42 is accepted in Free and the user later chooses Work
- **THEN** the remembered scene brightness observed on return is 42, as it would be after a change in the Nanoleaf app

#### Scenario: Free handoff clears an override

- **WHEN** a brightness override is active in Work and the user chooses Free
- **THEN** the override is cleared, Free performs its existing one-time handoff, and no later Free polling occurs

### Requirement: Saved scenes are discovered and activated only in Free

The worker's existing scene observation SHALL record the device's saved scene identities, bounded to 256, as opaque neutral IDs that reveal no scene name in the shared snapshot. `scene.activate` SHALL be accepted only when the desired mode is Free; in Work or Quiet it SHALL return the typed `unsupported-capability` failure before any device write, with a replayable receipt and no new wire value. In Free it SHALL perform one selection write through the worker, start no polling, and preserve task pulse epochs, comet sources, unread tracking and reservations. This requirement maps to issue #64 AC4.

#### Scenario: Scene requested in Work

- **WHEN** a client requests a discovered scene while the desired mode is Work or Quiet
- **THEN** the request fails with `unsupported-capability`, the failure receipt is retained for replay, and the device receives no write

#### Scenario: Scene activated in Free

- **WHEN** a client requests a discovered scene while the desired mode is Free
- **THEN** the worker sends exactly one selection write, the receipt reports transmission, and the worker performs no further controller polling in Free

#### Scenario: Unknown scene identity

- **WHEN** a client requests a scene ID that discovery has not advertised
- **THEN** the request fails with `unsupported-capability` and nothing is written

### Requirement: Desired general-control state stays separate from observation

Snapshots SHALL report desired power and brightness as known only while an override is active and as unknown otherwise, alongside the desired mode; pending general controls SHALL appear in the bounded pending list; last successful send, last outcome and observation SHALL remain separate, and observation SHALL stay unknown unless the worker holds evidence. This requirement maps to issue #64 AC5.

#### Scenario: Snapshot after an accepted brightness command

- **WHEN** a client reads the snapshot after `brightness.set` is accepted and before the worker sends it
- **THEN** desired brightness is known, the command is pending, last successful send is unchanged and observation remains unknown

#### Scenario: Snapshot after a mode command

- **WHEN** a client reads the snapshot after an explicit mode command clears the overrides
- **THEN** desired power and brightness are unknown again and the desired mode reflects the command

### Requirement: Supported modes preserve Linux ownership

The controller SHALL advertise Work, Quiet and Free as supported modes, power as supported, brightness as supported with the typed 0 to 100 bound, and scenes as supported with the discovered saved-scene identities bounded to 256 IDs; media, zones and preview SHALL remain unsupported. Accepted mode requests SHALL use the installation's existing Linux state coordination and single light worker. Existing mode brightness, scene restoration, pulse timing, unread behavior, project reservations SHALL remain intact. Installed commands SHALL open only the installation's own Linux state; no command SHALL forward to another operating system. This requirement maps to issue #28's worker-ownership and unavailable-preview criteria, to [issue #64](https://github.com/jimmie-potts/codex-nanoleaf/issues/64) AC1 and to [issue #131](https://github.com/jimmie-potts/codex-nanoleaf/issues/131) AC1 and AC2; the retained baseline is the [bridge guide](../../../bridge/README.md).

#### Scenario: A client requests Quiet

- **WHEN** an authorized fresh command requests Quiet
- **THEN** the existing worker applies the current Quiet policy and the API does not independently send a light request

#### Scenario: A client requests unsupported brightness or preview

- **WHEN** a client inspects capabilities, requests a brightness outside 0 to 100, or requests a media, zone or preview operation
- **THEN** power, brightness and scenes are declared supported with their typed constraints, the out-of-range brightness fails validation, media, zones and preview are explicitly unavailable, and the unsupported operation is rejected through the shared contract without a new effect

#### Scenario: Linux-owned controller command

- **WHEN** a controller command targets the Linux installation
- **THEN** it uses only that installation's Linux state and worker, and the installed command surface contains no forwarding entry point

### Requirement: Per-device controller ledgers

The controller SHALL keep one ledger per configured device, with its own identity and epoch, configuration revision, generation, request journal and sequence, event feed, saved-scene identities, overrides and hold. The original ledger SHALL keep its identity, epoch, retained receipts, cursor and scene IDs in storage that older source can still read and write. Removing a device SHALL delete its ledger. `controller-configure` SHALL add a ledger only for a registered device other than the original one, with the original controller and source IDs, and SHALL still reject redirecting an existing identity. `/controller/v1/devices` SHALL list every configured device's snapshot, the original first. Snapshot, feed and command routes SHALL select the ledger named by `deviceId`, and one credential SHALL authorize every configured device. Power, brightness, mode and `scene.activate` SHALL follow the same mode rules on every device. This requirement maps to [issue #113](https://github.com/jimmie-potts/codex-nanoleaf/issues/113) scope 1 and 3 and AC1.

#### Scenario: Both devices are listed

- **WHEN** Lines and Panels ledgers are configured and an authorized client reads `/controller/v1/devices`
- **THEN** it receives two snapshots, Lines first, each with its own device identity, epoch, revision, generation and scene IDs

#### Scenario: Adding a registered device

- **WHEN** the operator configures the registered Panels with the original controller and source IDs
- **THEN** a Panels ledger with a new epoch is created, repeating the command changes nothing, the original ledger is unchanged, and configuring an unregistered device or a different controller ID is rejected

#### Scenario: Scene activation on the Panels in Work

- **WHEN** a client activates an advertised Panels scene while the Panels are in Work and the Lines are in Free
- **THEN** the request fails with `unsupported-capability` and a retained receipt, and neither device receives a write

#### Scenario: Existing ledger stays compatible with older source

- **WHEN** an installation with a pre-change single ledger, retained receipts and a hold is opened and a Panels ledger is added
- **THEN** the original tables' schema and rows are unchanged and still accept the older source's writes, the hold survives, and a retained request replays its original receipt

#### Scenario: Removing the Panels

- **WHEN** the operator removes the Panels after they were added to the controller
- **THEN** their ledger is deleted, `/controller/v1/devices` lists only the Lines, and a later Panels request is forbidden
