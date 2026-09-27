## ADDED Requirements

### Requirement: Hub-paired runs

The `hub-paired` scenario SHALL make a run a consumer of a paired Hub run. It SHALL require the `hub-feed` run input, the Hub run's origin `http://127.0.0.1:<port>/`, and SHALL refuse any other form or an installed service's port (8788, 8765, 8787, 8791, 41230, 41231). It SHALL read two credential files from the run's runtime directory, `hub-feed-token` and `hub-controller-token`. Each SHALL be a private regular file owned by the user, not a symlink, holding one 43-character base64url token. A missing or unusable file SHALL fail the seed with a fixed line naming the file, without a path or value, and write nothing. The seed SHALL leave no local tasks or synthetic projects. It SHALL give the controller the identity `wall-controller`, device `wall`, source `wall`, and accept the Hub's controller token as principal `hub` with read and control scopes, stored only as its digest. It SHALL select shared input following `<hub-feed>api/monitor/v1` with owner `verify-owner`, consumer `nanoleaf` and the one qualified source `{codex, cli, verify-host, verify-source}`, reading the feed token from its file. `serve` SHALL then run the real controller API listener, announced as the `controller` endpoint `http://127.0.0.1:<port>/`; for port 0 it SHALL take a port no installed service uses. If that listener stops after it was announced, the run SHALL print the fixed line `controller listener stopped` and exit with status 1. It SHALL also run a worker stand-in that, about once per second and whenever the map or controller wakes it, polls the feed through the real shared-input Poller, applies the integration settings queue, pending edits and allocation, and never renders or sends. Once a run has announced the controller endpoint, every later scenario SHALL announce it again on the same port; a standalone scenario SHALL accept no Hub credential there. Every run SHALL serve a read-only `GET /verify/state` on its map origin, under the map's Host check and without a credential. It SHALL report the scenario, the feed's source, connection, applied revision, receipt time, fixed error code and the owner of the last accepted snapshot, null before the first and never the configured owner in its place, and counts of the Lines' integration settings requests that were applied, are queued or failed. It SHALL never report a token or a token path. A `hub-paired` run SHALL serve the page at `/` with its header B.U.N.N.Y. link leading to the `hub-feed` origin instead of the installed Hub, changing nothing else in the page. It SHALL answer 503 instead when the page does not hold the installed link exactly once. Every other scenario SHALL serve the page unchanged apart from its edit token. (Issue #194: the Hub's controller calls reach the wall's real controller API, and the wall paints Hub-fed lifecycle state. Hub #495: no preview link leads to an installed service.)

#### Scenario: Paired seed
- **WHEN** `hub-paired` is seeded with a paired Hub origin and both credential files
- **THEN** the controller identity is `wall-controller`/`wall`/`wall`, principal `hub` is stored by its token's digest, shared input follows the Hub feed with owner `verify-owner`, and no file in the state directory holds either token

#### Scenario: Unusable credentials or origin
- **WHEN** a credential file is missing, readable by others, a symlink or malformed, or `hub-feed` is not exactly a loopback origin or names an installed port
- **THEN** the seed fails with a fixed line, and the state directory stays empty

#### Scenario: The Hub's controller calls
- **WHEN** a caller presents the Hub's controller token to the announced controller endpoint
- **THEN** `/controller/v1/devices` lists the `wall-controller` identity, an integration settings command is admitted and the stand-in applies it, and a request without a credential or with the feed token is unauthenticated

#### Scenario: Hub-fed lifecycle state
- **WHEN** the paired Hub serves sessions from the qualified source and from another source
- **THEN** the map lists each qualified session with the status, title and evidence the feed gives, paints its Line in that status's color, and shows nothing from the other source

#### Scenario: A Hub that refuses at first
- **WHEN** the Hub rejects the feed credential after the seed and accepts it later
- **THEN** the run keeps serving with the feed `unavailable`, error `feed-rejected` and no owner, then becomes current at the Hub's revision, with owner `verify-owner`, without a restart

#### Scenario: A controller listener that stops
- **WHEN** a paired run's controller listener stops after it was announced
- **THEN** the run prints `controller listener stopped` and exits with status 1

#### Scenario: A Hub that goes away
- **WHEN** the Hub stops answering after the wall accepted its snapshot
- **THEN** the feed reads `stale` with `feed-unavailable` and every Hub-fed task reports uncertain evidence

#### Scenario: The page's link to the Hub
- **WHEN** a `hub-paired` run and a standalone run serve the map page
- **THEN** the paired page equals `bridge/wall.html`, with its token and with the B.U.N.N.Y. link's target replaced by the `hub-feed` origin, and names no installed port; the standalone page equals `bridge/wall.html` with its token; and a page without exactly one installed link is refused

#### Scenario: Relaunch keeps the controller port
- **WHEN** a paired run is reseeded to a standalone scenario, or to hub-paired again, on its recorded ports
- **THEN** the controller answers on the same port, refusing the Hub's token in the standalone scenario and accepting it in hub-paired

## MODIFIED Requirements

### Requirement: Named synthetic scenarios

The demo SHALL seed a named scenario into an empty, caller-owned state directory: the Lines and Light Panels registry and fixture layouts, synthetic projects and tasks, and the hook waits behind blocked and question tasks. `hub-paired` instead seeds no tasks or projects and pairs with a Hub run as the Hub-paired runs requirement describes. It SHALL mark the directory with `demo-run.json` naming the scenario and, for `hub-paired`, the paired Hub's port. The `reference` scenario SHALL match the browser suite's fixture. `layout-unavailable` SHALL save Line positions without drawing geometry. Seeding a standalone scenario SHALL be deterministic for a fixed clock. Seeding SHALL refuse an unknown scenario, a non-empty directory, or the installation's state directory or a directory inside it, without writing; `demo.py seed` SHALL exit with status 2 for the installation's state directory. (Issue #193: fresh documented runs cover Lines and Panels.)

#### Scenario: Reference seed
- **WHEN** `reference` is seeded
- **THEN** five tasks in all four statuses are placed on both devices, task-1 waits on a shell approval and task-2 on an asynchronous question

#### Scenario: Refused seed
- **WHEN** the scenario is unknown or the directory already holds state
- **THEN** seeding fails and the directory is unchanged

#### Scenario: Marked directory
- **WHEN** a scenario is seeded
- **THEN** the directory holds `demo-run.json` naming that scenario

#### Scenario: Seed refuses the installation's state
- **WHEN** `demo.py seed` is given the installation's state directory, or a directory inside it, under the user's home
- **THEN** it exits with status 2 without a traceback and writes nothing

### Requirement: Served run on its own port and state

`demo.py serve` SHALL start the wall server as the installed map starts, including its bounded layout retries, over the given state directory, bound to `127.0.0.1` on the requested port, where 0 lets the kernel choose. With `--controller-port` it SHALL also serve the controller API on `127.0.0.1` at that port, 0 letting the kernel choose, and announce it in the ready line's `endpoints` as `controller`. It SHALL write `map-server.json` with its port, instance and boundary. It SHALL print one ready line with its URL and instance, never print the page's edit token or a credential, and exit on SIGTERM leaving the directory to its owner. `serve` and `drive` SHALL refuse, with exit status 2 and without writing, a directory that `seed` did not mark and the installation's state directory or a directory inside it. (Issue #193: two runs share nothing.)

#### Scenario: Ready run
- **WHEN** a seeded directory is served on port 0
- **THEN** the ready line names a loopback URL whose `/health` reports the same instance, and the map page and state answer from that directory

#### Scenario: Relaunch after a reseed
- **WHEN** the directory is emptied, reseeded and served on the recorded port
- **THEN** the run answers on the same port with the new scenario's state

#### Scenario: Independent runs
- **WHEN** two runs serve at once and one is driven
- **THEN** they use different ports and the other run's state is unchanged

#### Scenario: Refused state directory
- **WHEN** `serve` or `drive` is given an unmarked directory, or the installation's state directory under the user's home
- **THEN** it exits with status 2, and neither the directory's state nor its `map-server.json` changes

#### Scenario: Controller port in use
- **WHEN** the requested controller port is already bound
- **THEN** the start fails, and the plug-in names it `wall-start-failed: controller port already in use`

### Requirement: Device boundary

Every demo entry point SHALL, before calling any bridge function, refuse outbound socket connections, datagram sends, new processes (the audited process events and the unaudited launcher that multiprocessing's spawn and forkserver use), foreign libraries and symbols loaded through ctypes, on Python 3.14 any foreign call through ctypes, and new subinterpreters, and SHALL route the wall server's light-request seam to a trap. The one exception: in a `hub-paired` run, `serve` and `drive` SHALL allow a TCP connection to `127.0.0.1` on the paired Hub's port, never an installed service's port, and record it as `allowed` with the address the process asked for. `seed` SHALL allow nothing. Each refusal SHALL be appended to the run's `device-boundary.jsonl` with its kind, target and time and SHALL NOT include a credential. The wall server SHALL treat a refusal as an unreachable device. (Issue #193: device-request traps fail on attempted physical requests. Issue #194: the boundary log shows only the paired port as allowed.)

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

#### Scenario: The paired port only
- **WHEN** a paired process connects to the paired Hub's port, another loopback port and an installed port, and sends a datagram to the paired port
- **THEN** only the first reaches its listener and is recorded `allowed`, the others are refused and recorded, and a test backstop beneath the boundary sees none of them

#### Scenario: The test backstop sees a boundary that lets a connection through
- **WHEN** the boundary's rule is replaced with one that allows everything and a paired process connects to another loopback listener beneath the test backstop
- **THEN** the boundary records that listener's address as `allowed`, and the backstop records and refuses the connection, which never reaches the listener

#### Scenario: An installed port named as the paired port
- **WHEN** a boundary is given an installed service's port as its paired port
- **THEN** it allows no connection, and a connection to that port is refused and recorded

### Requirement: Driven task transitions

`demo.py drive` SHALL apply a named transition's hook events through the actual hook handler and the worker stand-in, and SHALL refuse an unknown transition without changing state. Transitions marked as defects SHALL be known-wrong inputs or a known-wrong stand-in that tries to send the effect to each device. A `hub-paired` run SHALL refuse hook transitions, because the Hub owns its task state, and SHALL take only its own defects: the paired stand-in polling the installed Hub's port 8788 through the real shared-input transport, and the paired stand-in sending the effect to each device. A standalone run SHALL refuse those defects. (Issue #193: task transitions. Issue #194: a connect to an installed port, or a light request, is refused.)

#### Scenario: Completion
- **WHEN** `complete` is driven on `reference`
- **THEN** task-0 becomes unread on the same Line and each device in Work queues its completion comet

#### Scenario: Defect transitions
- **WHEN** `defect-approve-other-tool` or `defect-complete-stale-turn` is driven
- **THEN** task-1 stays blocked and task-0 stays working

#### Scenario: A stand-in that contacts the devices
- **WHEN** `defect-complete-contacts-device` is driven
- **THEN** task-0 becomes unread, and the stand-in's effect request to each device is refused and recorded

#### Scenario: Paired defects
- **WHEN** `defect-poll-installed-hub` or `defect-paired-light-request` is driven on a `hub-paired` run
- **THEN** the connection to `127.0.0.1:8788`, or each device's effect request, is refused and recorded before any byte is sent

#### Scenario: Transitions that belong to the other kind of run
- **WHEN** a hook transition is driven on a `hub-paired` run, or a paired defect on a standalone run
- **THEN** it is refused and the state is unchanged

### Requirement: Assertion-backed capture steps

The wall plug-in SHALL define capture steps for the Lines wall, a task completion, an approval, an approval request, a resumed task, the Project layout configuration, the lighting modes with assembly replay and reduced motion, the Light Panels, the refused device read and the Hub-fed lifecycle state of a `hub-paired` run. Each step SHALL record named assertions on the page's painted colors, listed statuses, alerts or renderer state. It SHALL assert that the page requested only its run origin and that the run recorded no device attempt during the step. The refused-read step instead SHALL require its startup layout read to have been refused, and SHALL accept during the step only the map's bounded layout retries: `GET` requests for the whole layout of `192.0.2.1`, at most three since the seed, each recorded at least 9.9 s after the previous one. The Hub-fed step SHALL accept during the step only allowed connections to the paired Hub's port. It SHALL read the Hub's feed with the wall's feed credential, wait until the wall is current at the Hub's revision, retrying a failed read of either within that wait, and derive each qualified top-level session's task key, status, title and evidence from the shared-input guide. It SHALL require at least one such session and every one of them to be placed on a Line, and compare them with the page's listed statuses, titles, evidence and painted Line colors. It SHALL require the header's one B.U.N.N.Y. link to lead to the `hub-feed` origin in a new tab, and the wall to stay current at that revision to the end of the step. Every step SHALL be fresh, so the core reseeds its scenario and relaunches the wall on the same port before it runs, and every capture's log SHALL name the demo entry that served and drove it. (Issue #193: presentation, configuration and animation states; screenshot and video. Issue #194: one capture step shows Hub-fed lifecycle state painted on the wall.)

#### Scenario: Reference steps
- **WHEN** each reference step runs through the core's capture driver
- **THEN** every assertion passes and a screenshot and a finalized video exist

#### Scenario: Transition keeps its Line
- **WHEN** a transition step drives `complete`, `approve`, `request-approval` or `resume`
- **THEN** the task is listed in its new status on the same Line, that Line is painted in the new status color, every other Line keeps its colors and the alerts match the new state

#### Scenario: A predicate check sees a wrong observation
- **WHEN** a step's check resolves `false`, or returns a value other than `true`, instead of throwing
- **THEN** the capture fails at that assertion

#### Scenario: Reduced motion
- **WHEN** the lighting-modes step switches the page to reduced motion in Work
- **THEN** the light phase holds still and Replay does not animate

#### Scenario: The map retries its layout read during the refused-read step
- **WHEN** the refused-read step starts 10 s or more after the wall, so the map retries its layout read during the step
- **THEN** the step passes, and any other device attempt would fail it

#### Scenario: A map that reads its layout on every poll
- **WHEN** the wall reads its layout on every poll and the refused-read step runs
- **THEN** the capture fails at "the only device attempts during the step are the map's bounded layout reads"

#### Scenario: Hub-fed lifecycle step
- **WHEN** `hub-lifecycle-painted` runs against a run paired with a stand-in Hub feed, or with a real Hub run
- **THEN** every assertion passes, the capture holds a screenshot and a finalized video, and no credential appears in its log

#### Scenario: A brief Hub outage or a session without a Line
- **WHEN** the Hub answers 503 for the first moments of the Hub-fed step, or serves more sessions than the wall has Lines
- **THEN** the step passes once the Hub answers again, and fails at "each Hub-fed task is placed on a Line" when a session waits for a Line

#### Scenario: A paired page that keeps the installed link
- **WHEN** a paired run serves its page with the B.U.N.N.Y. link still leading to `http://127.0.0.1:8788/`
- **THEN** `hub-lifecycle-painted` fails at "the B.U.N.N.Y. link leads to the paired Hub run"

### Requirement: Negative controls fail

The plug-in SHALL define negative controls that apply a known-wrong transition, serve a known-wrong page, or use a stand-in that contacts the devices or the installed Hub, to the same assertions. Each control SHALL fail at its named assertion rather than crash. A presentation control SHALL first assert that its page change was applied exactly once. (Issue #193: a known defect is detected and reference behavior passes. Issue #194: a negative control fails.)

#### Scenario: Stale completion
- **WHEN** `control-stale-completion` runs
- **THEN** the capture fails at "task-0 reads unread in the task list"

#### Scenario: Unread painted as working
- **WHEN** `control-unread-painted-working` runs
- **THEN** the capture fails at "task-0's Line is painted in the unread color"

#### Scenario: Stale red
- **WHEN** `control-stale-red` runs
- **THEN** the capture fails at "task-1 reads working in the task list"

#### Scenario: Device attempt during a step
- **WHEN** `control-device-attempt` runs
- **THEN** the capture fails at "no device attempt was recorded during the step", and its boundary record lists both refused effect requests

#### Scenario: A paired stand-in that polls an installed port
- **WHEN** `control-paired-installed-port` runs
- **THEN** the capture fails only at "only the paired Hub feed was contacted during the step", its boundary record lists the refused connection to `127.0.0.1:8788`, and the test backstop saw nothing

#### Scenario: A paired stand-in that sends a light request
- **WHEN** `control-paired-light-request` runs
- **THEN** the capture fails only at "only the paired Hub feed was contacted during the step", and its boundary record lists both refused effect requests

### Requirement: Labelled components and boundary check

The plug-in SHALL label the wall server, page, state store, hook handler, allocation, controller API, shared input and integration settings as actual, and the light worker, both devices and the Codex metadata as simulated. Its `device-boundary` check SHALL run at start and in `doctor`. It SHALL fail when a standalone scenario other than `layout-unavailable` recorded any entry since its last seed. For `layout-unavailable` it SHALL fail when the log holds anything other than the map's layout reads of the Lines, `GET` requests for the whole layout of `192.0.2.1`, when it holds none, or when it holds more than three or two recorded less than 9.9 s apart. For `hub-paired` it SHALL fail on any entry other than an allowed connection to the paired Hub's port, and when the run has no paired port. Its `paired-feed` check SHALL run at start and in `doctor`. It SHALL be `skipped` for a standalone scenario. For `hub-paired`, until the wall has accepted a snapshot since its seed, it SHALL be `skipped` within 30 s of the seed, while the Hub is plausibly not yet configured to accept the wall, and `failed` after that, naming the feed's error code, because the pairing never came up. Once the wall has a snapshot it SHALL pass only when the wall's feed is current at the revision the Hub serves, reading the Hub with the wall's feed credential from a private regular file, never through a symlink. It SHALL fail when the feed stays stale, or the revision behind, for about 3 s. Its readiness probe SHALL fail for an installed service port or a map instance other than the run's own. It SHALL fail for a `hub-paired` map without the paired boundary. It SHALL fail for an announced controller endpoint that is not this run's listener or that answers a request without a credential with anything but `unauthenticated`. A failed start SHALL be named from the server's stderr by a fixed cause line or the Python exception type alone, never an exception message. A failed seed SHALL be named `demo.py seed failed: <cause>` from the same mapping, never with the command or its paths. Each capture, including a failed one, SHALL attach the boundary record of its step. (Issue #193: identify real and simulated components. Issue #194: a doctor check that the paired feed is current and its revision matches.)

#### Scenario: Another map on the port
- **WHEN** the run's receipt names an instance that `/health` does not report
- **THEN** the probe fails with the reason that health names another map instance

#### Scenario: Unexpected attempts in layout-unavailable
- **WHEN** a `layout-unavailable` run's log holds a process, socket or other light request beside the layout read
- **THEN** the device-boundary check fails

#### Scenario: Unexpected entries in hub-paired
- **WHEN** a `hub-paired` run's log holds a refused entry, a light request, a datagram or an allowed connection to another port
- **THEN** the device-boundary check fails, while a log of allowed connections to the paired port passes

#### Scenario: A failed capture keeps its boundary record
- **WHEN** a capture fails at an earlier assertion
- **THEN** its capture still holds `device-boundary.json` for its step

#### Scenario: A failed seed
- **WHEN** `demo.py seed` fails during `start` with a Python error
- **THEN** `failure.detail` names the fixed cause, and neither the command, the interpreter path nor the checkout path appears in the result, the receipt or the events

#### Scenario: The paired feed check
- **WHEN** a paired run's Hub has not yet accepted the wall's credential, then accepts it, then serves a snapshot from another owner or stops answering
- **THEN** `paired-feed` reads skipped, then passed, then failed with the stale or mismatched reason

#### Scenario: A pairing that never comes up
- **WHEN** a paired run has accepted no snapshot 30 s after its seed
- **THEN** `paired-feed` fails, naming the feed's error code

### Requirement: Supervised runs through the shared core

`npm run verify -- <operation>` SHALL run the shared core's operations with the wall plug-in, named `wall`, whose default scenario is `reference`. The plug-in SHALL declare the one optional input `hub-feed`, which only `hub-paired` requires. The receipt SHALL name the checkout's revision and dirty flag and a digest of the page and its three Prism assets. A run SHALL start only after its ready line, its probe and its boundary checks pass. The repository SHALL check the supervised lifecycle against real transient user units where a user manager exists, and SHALL skip with the reason printed where none exists. (Issue #193: two runs share nothing; failed starts and expired leases clean only owned resources; a handoff is reproducible after expiry without modifying retained proof. Issue #194: adapter tests and a local paired run.)

#### Scenario: Run, proof and cleanup
- **WHEN** a run starts, captures, hands off with a reset, captures again, extends and stops
- **THEN** the receipt validates, doctor reads it running with a passing probe and a matching artifact, the verified set keeps its checksums through the later capture and the extension, and stop removes the unit, lease timer and runtime directory

#### Scenario: A start that attempts a device request
- **WHEN** the served state makes the wall ask a device for its layout during a `reference` start
- **THEN** the device-boundary check fails the start and the start leaves no unit, timer or runtime directory

#### Scenario: Failed, interrupted and expired runs
- **WHEN** the wall exits before readiness, a start is killed after seeding, or a lease expires after handoff
- **THEN** doctor lists the run as failed, starting or expired, stop removes only what that run created, and frozen proof still verifies

#### Scenario: Concurrent runs and restart
- **WHEN** two runs serve at once and one is reseeded, or a run is restarted
- **THEN** the other run keeps its state and process, and the restarted run names its predecessor and whether the candidate is the same

#### Scenario: Restart after expiry
- **WHEN** an expired, handed-off run is handed off again and then restarted
- **THEN** the handoff reports `run-not-running`, the new run names the expired run and whether the candidate is the same, and the expired run's verified `SHA256SUMS` is unchanged

#### Scenario: A supervised paired run
- **WHEN** a standalone run's credential files are written and it is reseeded `hub-paired` with a stand-in Hub's origin, captured, and reseeded `reference`
- **THEN** the reseed announces the controller endpoint, the Hub's token reaches the controller API, doctor reads both checks passed and the endpoint's listener matching, the Hub-fed step passes, the receipt records the input and endpoint, the standalone reseed keeps the endpoint on its port and refuses the Hub's token, and no proof file holds a credential

#### Scenario: A paired reseed without credential files
- **WHEN** a run is reseeded `hub-paired` before the credential files exist
- **THEN** the reseed fails naming the missing file without a path, and the core stops only that run
