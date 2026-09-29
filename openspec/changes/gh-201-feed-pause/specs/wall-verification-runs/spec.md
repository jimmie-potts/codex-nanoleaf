## ADDED Requirements

### Requirement: Disposable paired feed pause

An explicitly launched `hub-paired` verification process SHALL honor a private versioned pause request for its run and nonce. It SHALL stop admitting Hub feed requests and forwarded Hub commands, drain requests already in flight, then atomically acknowledge the matching run and nonce with its own process identity. While paused, local pages, health and controller reads SHALL remain responsive, retained feed state SHALL preserve truthful freshness, and no rejected command SHALL be queued for replay. Invalid, linked, oversized, nonprivate or wrong-run controls SHALL block admission without a successful acknowledgment. Ordinary launches SHALL NOT enable this mechanism through inherited environment alone.

#### Scenario: A request already in flight
- **WHEN** a pause arrives while a Hub response is unfinished
- **THEN** no acknowledgment appears until that request drains, then a matching process acknowledgment appears and subsequent timer and read activity makes no new Hub request

#### Scenario: Responsive paused preview
- **WHEN** an owner reads pages or controller state and attempts a Hub command after pause acknowledgment
- **THEN** local reads answer, the feed does not claim fresh observation without evidence, the Hub command is refused and never replayed, and no new Hub request starts

#### Scenario: Resume a live consumer
- **WHEN** the pause request is removed without reseeding
- **THEN** the still-running consumer resumes normal polling without replaying a refused command

#### Scenario: Invalid controls or ordinary startup
- **WHEN** a control file is malformed, linked, nonprivate or for another run, or pause settings are inherited by an ordinary launch
- **THEN** the paired process does not acknowledge unsafe controls, and ordinary startup retains its existing behavior without enabling the pause mechanism

### Requirement: Authorized paired reseed release

A seed encountering a pause SHALL refuse to proceed unless it is `hub-paired` and has a matching one-shot release authorization. It SHALL preserve the pause on failed or unrelated seeding. A successful authorized seed SHALL consume the same pause and release only after the old process has stopped and fresh state has been written, before launching the new process. Reseeding SHALL preserve pairing token files, recorded ports and frozen proof. The new process SHALL accept the reseeded owner's current feed without retaining the prior owner's higher revision.

#### Scenario: Owner resets before consumer
- **WHEN** the coordinator authorizes the paused consumer's reseed after resetting the Hub owner
- **THEN** the old consumer stops, fresh paired state is seeded, the matching controls are consumed, and the new consumer reaches current-feed readiness at the owner's new revision on its recorded ports

#### Scenario: Missing, stale or failed release
- **WHEN** a seed lacks matching release authorization, targets another scenario, sees a newer pause request, or fails before completion
- **THEN** it does not resume the paused feed, retains the outstanding controls and remains stoppable without changing frozen proof

## MODIFIED Requirements

### Requirement: Labelled components and boundary check

The plug-in SHALL label the wall server, page, state store, hook handler, allocation, controller API, shared input and integration settings as actual, and the light worker, both devices and the Codex metadata as simulated. Its `device-boundary` check SHALL run at start and in `doctor`. It SHALL fail when a standalone scenario other than `layout-unavailable` recorded any entry since its last seed. For `layout-unavailable` it SHALL fail when the log holds anything other than the map's layout reads of the Lines, `GET` requests for the whole layout of `192.0.2.1`, when it holds none, or when it holds more than three or two recorded less than 9.9 s apart. For `hub-paired` it SHALL fail on any entry other than an allowed connection to the paired Hub's port, and when the run has no paired port. Its `paired-feed` check SHALL run at start and in `doctor`. It SHALL be `skipped` for a standalone scenario. For `hub-paired`, until the wall has accepted a snapshot since its seed, it SHALL be `skipped` within 30 s of the seed, while the Hub is plausibly not yet configured to accept the wall, and `failed` after that, naming the feed's error code, because the pairing never came up. Once the wall has a snapshot it SHALL pass only when the wall's feed is current at the revision the Hub serves, reading the Hub with the wall's feed credential from a private regular file, never through a symlink. It SHALL fail when the feed stays stale, or the revision behind, for about 3 s. Its readiness probe SHALL fail for an installed service port or a map instance other than the run's own. It SHALL fail for a `hub-paired` map without the paired boundary. It SHALL fail for an announced controller endpoint that is not this run's listener or that answers a request without a credential with anything but `unauthenticated`. A failed start SHALL be named from the server's stderr by a fixed cause line or the Python exception type alone, never an exception message. A failed seed SHALL be named `demo.py seed failed: <cause>` from the same mapping, never with the command or its paths. Each capture, including a failed one, SHALL attach the boundary record of its step. (Issue #193: identify real and simulated components. Issue #194: a doctor check that the paired feed is current and its revision matches.)


While a valid verification feed pause is active, the paired-feed diagnostic SHALL report `skipped` with a pause reason without probing the Hub. Invalid pause control state SHALL report `failed` without probing the Hub. A paused diagnostic SHALL NOT establish composition readiness; the ordinary current-feed check SHALL pass after authorized reseed release.

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

