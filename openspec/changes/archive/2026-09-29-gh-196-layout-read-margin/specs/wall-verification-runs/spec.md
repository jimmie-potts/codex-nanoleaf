## MODIFIED Requirements

### Requirement: Assertion-backed capture steps

The wall plug-in SHALL define capture steps for the Lines wall, a task completion, an approval, an approval request, a resumed task, the Project layout configuration, the lighting modes with assembly replay and reduced motion, the Light Panels, the refused device read and the Hub-fed lifecycle state of a `hub-paired` run. Each step SHALL record named assertions on the page's painted colors, listed statuses, alerts or renderer state. It SHALL assert that the page requested only its run origin and that the run recorded no device attempt during the step. The refused-read step instead SHALL require its startup layout read to have been refused, and SHALL accept during the step only the map's bounded layout retries: `GET` requests for the whole layout of `192.0.2.1`, at most three since the seed, each recorded at least 9 s after the previous one. The Hub-fed step SHALL accept during the step only allowed connections to the paired Hub's port. It SHALL read the Hub's feed with the wall's feed credential, wait until the wall is current at the Hub's revision, retrying a failed read of either within that wait, and derive each qualified top-level session's task key, status, title and evidence from the shared-input guide. It SHALL require at least one such session and every one of them to be placed on a Line, and compare them with the page's listed statuses, titles, evidence and painted Line colors. It SHALL require the header's one B.U.N.N.Y. link to lead to the `hub-feed` origin in a new tab, and the wall to stay current at that revision to the end of the step. Every step SHALL be fresh, so the core reseeds its scenario and relaunches the wall on the same port before it runs, and every capture's log SHALL name the demo entry that served and drove it. (Issue #193: presentation, configuration and animation states; screenshot and video. Issue #194: one capture step shows Hub-fed lifecycle state painted on the wall. Issue #196: a layout read recorded late does not fail a correct map.)

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

#### Scenario: A layout read recorded late
- **WHEN** the map decides its layout reads 10 s apart and one of them is recorded 500 ms late
- **THEN** the refused-read step's layout-read bound still holds

### Requirement: Labelled components and boundary check

The plug-in SHALL label the wall server, page, state store, hook handler, allocation, controller API, shared input and integration settings as actual, and the light worker, both devices and the Codex metadata as simulated. Its `device-boundary` check SHALL run at start and in `doctor`. It SHALL fail when a standalone scenario other than `layout-unavailable` recorded any entry since its last seed. For `layout-unavailable` it SHALL fail when the log holds anything other than the map's layout reads of the Lines, `GET` requests for the whole layout of `192.0.2.1`, when it holds none, or when it holds more than three or two recorded less than 9 s apart. For `hub-paired` it SHALL fail on any entry other than an allowed connection to the paired Hub's port, and when the run has no paired port. Its `paired-feed` check SHALL run at start and in `doctor`. It SHALL be `skipped` for a standalone scenario. For `hub-paired`, until the wall has accepted a snapshot since its seed, it SHALL be `skipped` within 30 s of the seed, while the Hub is plausibly not yet configured to accept the wall, and `failed` after that, naming the feed's error code, because the pairing never came up. Once the wall has a snapshot it SHALL pass only when the wall's feed is current at the revision the Hub serves, reading the Hub with the wall's feed credential from a private regular file, never through a symlink. It SHALL fail when the feed stays stale, or the revision behind, for about 3 s. Its readiness probe SHALL fail for an installed service port or a map instance other than the run's own. It SHALL fail for a `hub-paired` map without the paired boundary. It SHALL fail for an announced controller endpoint that is not this run's listener or that answers a request without a credential with anything but `unauthenticated`. A failed start SHALL be named from the server's stderr by a fixed cause line or the Python exception type alone, never an exception message. A failed seed SHALL be named `demo.py seed failed: <cause>` from the same mapping, never with the command or its paths. Each capture, including a failed one, SHALL attach the boundary record of its step. (Issue #193: identify real and simulated components. Issue #194: a doctor check that the paired feed is current and its revision matches. Issue #196: a layout read recorded late does not fail a correct map.)

While a valid verification feed pause is active, the paired-feed diagnostic SHALL report `skipped` with a pause reason without probing the Hub. Invalid request or release input, including release for another nonce or without a request, SHALL report `failed` without probing the Hub. A paused diagnostic SHALL NOT establish composition readiness; the ordinary current-feed check SHALL pass after authorized reseed release.

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

#### Scenario: Diagnostic during a feed pause
- **WHEN** a paired-feed diagnostic runs while valid or invalid pause control state is present
- **THEN** it reports skipped or failed respectively without making a Hub request and does not claim readiness

#### Scenario: Layout reads late, too frequent or too many
- **WHEN** a `layout-unavailable` run's log holds three layout reads decided 10 s apart with the first recorded 500 ms late, or two reads 1 s apart, or four reads 10 s apart
- **THEN** the device-boundary check passes the first log and fails the second on the spacing and the third on the count
