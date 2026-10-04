# Development and deployment

The repository is the canonical source. Fresh Linux setup and service operation follow [the Linux installation guide](linux-install.md); its private runtime lives under `~/.local/share/codex-nanoleaf`. The retired Windows installation and the original scratch workspace are historical and are not used for future changes.

Follow [the SDLC guide](sdlc.md) for issue scope, planning, TDD, independent review,
and merge criteria. It also defines when installation is part of a task.

## Validate a change

Run `python3 scripts/check.py` from the root. Install the optional controller dependencies first with `python3 -m pip install -r requirements-controller.txt`, preferably in an isolated virtual environment. They exercise status transitions, read handling, comets, scenes, modes, project placement, split rendering, metadata recovery, and local HTTP validation. A successful run contacts neither a controller nor the real Codex state.

Run `npm run test:browser` and `npm run test:verify` after map or API changes; the verification capture steps read the page's task list, painted Lines and renderer snapshot. `npm run test:browser` starts the synthetic demo on an available loopback port and shuts it down afterward. Screenshots are written to ignored `test-results/`. To inspect the map manually, run `python3 scripts/demo.py` and open its printed URL.

Exercise Linux installation and device enrollment with isolated state and fake device transport; never enroll a personal device from a development checkout. `cd tests && python3 -m unittest test_enrollment` runs the focused enrollment tests; the operator commands are in [the Linux installation guide](linux-install.md#add-nl22-light-panels). Hosted CI runs the Python, browser, MCP and workflow checks on Linux; there are no platform-specific checks.

## Diagnostic checks

The optional [controller and worker diagnostics](observability.md) use the pinned dependencies above. `python3 -m unittest discover -s tests -p test_observability.py` checks copied-package conformance and host integration with fake state/transport. `scripts/check.py` includes it in both Python CI jobs. Run it before the full Python, browser/API and workflow checks when changing these boundaries.

## Verification runs

A verification run serves the actual wall server over its own synthetic state. An agent can exercise a change, keep assertion-backed proof and hand over a disposable preview that expires. The shared lifecycle core `@jimmie-potts/app-verify`, vendored from the Hub under `vendor/`, implements the [app verification contract](https://github.com/jimmie-potts/agent-device-hub/blob/main/docs/app-verification.md): the transient systemd user unit and lease timer, receipt, `doctor`, frozen proof, capture harness and preview card. This repository supplies the wall plug-in in `scripts/verify/` and the wrapper `scripts/verify.mjs`. The [wall verification runs specification](../openspec/specs/wall-verification-runs/spec.md) owns the plug-in's requirements.

Run the operations from the checkout with Node 22 or later, Python 3.12 or later and a `systemd --user` manager. The `hub-paired` scenario also needs the controller dependencies in `requirements-controller.txt`:

```bash
npm run verify -- start [--scenario reference] [--lease 120]
npm run verify -- capture <run-id> <step>
npm run verify -- handoff <run-id> [--reset reference]
npm run verify -- doctor [<run-id>]
npm run verify -- scenario <run-id> <scenario> [--input hub-feed=http://127.0.0.1:<port>/]
npm run verify -- extend <run-id> [--lease <minutes>]
npm run verify -- stop <run-id>
npm run verify -- restart <run-id>
```

Each operation prints one JSON result line on stdout and its progress and preview card on stderr; `npm run -s verify -- …` leaves out npm's own banner lines. Exit status 0 means verified, 1 a failed outcome, 2 a usage error and 3 an unavailable supervisor or browser. Run ids look like `wall-20260927T074637Z-3e5e41`. Proof goes to the canonical checkout's ignored `.local/evidence/verify/<run-id>/`, even from a linked worktree. Runtime state goes to `~/.local/state/app-verify/<run-id>/`, and `stop` deletes it. Stop every run you start, then confirm with `doctor`. The preview URL is `http://127.0.0.1:<port>/`. The wall accepts only the `127.0.0.1` host, never `localhost`. A dirty checkout runs but is labelled `dirty`; proof for a merge candidate must come from a clean run.

The plug-in is built on these `scripts/demo.py` commands:

| Command | Effect |
| --- | --- |
| `python3 scripts/demo.py scenarios` | Print the scenario names and descriptions as JSON |
| `python3 scripts/demo.py seed --state-dir <dir> --scenario <name>` | Write a scenario into an empty directory: registry, layout, projects, tasks and hook waits, then mark it with `demo-run.json`. `hub-paired` also takes `--hub-feed <origin> --credentials <run directory>` |
| `python3 scripts/demo.py serve --state-dir <dir> --port 0 [--controller-port 0]` | Start the wall server as the installed map starts, on `127.0.0.1`, with its bounded layout retries. It writes `map-server.json` and prints one ready line, `{"url": …, "instance": …}`. With `--controller-port`, it also serves the controller API and adds `"endpoints": {"controller": "http://127.0.0.1:<port>/"}`. The page's edit token is never printed |
| `python3 scripts/demo.py drive --state-dir <dir> <transition>` | Apply a named task transition through the actual hook handler, then the worker stand-in. A `hub-paired` run takes only its own defect transitions |

`serve` and `drive` accept only a directory that `seed` marked with `demo-run.json`. Every command refuses the installation's own state directory, `~/.local/share/codex-nanoleaf` as the bridge resolves it, and any directory inside it. Each exits with status 2 and changes nothing.

Before calling any bridge function, every command installs a process boundary; importing the bridge modules first has no side effects. Apart from a `hub-paired` run's one allowed connection, described below, the boundary refuses outbound socket connections and datagram sends, new processes (the audited process events, plus the unaudited launcher that multiprocessing's spawn and forkserver use), foreign libraries and symbols loaded through ctypes, and new subinterpreters. On Python 3.14 it also refuses any foreign call through ctypes. Python 3.12 raises no audit event for a call through a function resolved before the boundary, and the demo and bridge never import ctypes. It also routes the wall server's light-request seam to a trap. Native extension code and libc resolver traffic are outside its reach, and no Nanoleaf path uses either. Each refusal is appended to `<dir>/device-boundary.jsonl` with its kind, target and time, never a credential. The wall server sees a refused request as an unreachable device.

The plug-in's readiness probe matches `map-server.json` against `/health`, so another listener on the port cannot pass. Its `device-boundary` check runs at start and again in `doctor`. It fails a run that recorded any device attempt since its last seed. There are two exceptions. `layout-unavailable` must record the map's layout reads, refused `GET` requests for the whole layout of `192.0.2.1`, and nothing else. It must record at least one, at most three, each at least 9 s after the previous one. `hub-paired` may record only allowed connections to its paired Hub's port. The `paired-feed` check is described under [Hub-paired runs](#hub-paired-runs). A failed start names its cause from the server's stderr with a fixed line, such as `wall-start-failed: port already in use`, or with the Python exception type alone, never an exception message. A failed seed is named the same way, as `demo.py seed failed: <cause>`, never with the command or its paths. The application runs with the core's private HOME and TMPDIR; the demo reads no home files. The artifact digest covers `bridge/wall.html` and its three Prism assets.

In a run, the wall server, map page, private SQLite state, hook handler and allocation are actual code. The light worker is a stand-in that applies edits and allocation and never renders or sends. The Lines (`192.0.2.1`) and Light Panels (`192.0.2.2`) are fixture layouts behind the boundary, and projects and tasks are synthetic. A run never reads Codex state, the installed runtime or its ports.

Scenarios:

- `reference`: the browser suite's fixture. Five tasks in all four statuses across three projects, on Lines and Light Panels in Work.
- `empty`: the same devices with no tasks.
- `layout-unavailable`: the reference tasks without saved drawing geometry. The map's startup asks the Lines for their layout, and the boundary refuses it.
- `hub-paired`: the same devices with no local tasks or projects, following a paired Hub run's session feed and serving the controller API that Hub calls. It needs the `hub-feed` input and two credential files; see [Hub-paired runs](#hub-paired-runs).

Every capture step is `fresh`: the core reseeds the step's scenario and relaunches the wall on the same port before the step runs, so each step's absolute observations start from known state. A fresh step after `handoff` also resets the preview. The capture browser prefers reduced motion; `lighting-modes` opts out to check the animation, then checks reduced motion itself.

| Behavior | Page entry | Driver action | Scenario | Capture step and expected observation |
| --- | --- | --- | --- | --- |
| Lines wall and task list | Open the map | None | `reference` | `wall-ready`: 15 Lines; each task listed with its status; alerts `1 blocked` and `1 question`; Device offers Lines and Light Panels; each placed task's Line painted in its status color |
| Task completion | None | `complete`: Stop for task-0 | `reference` | `task-completes`: task-0 listed unread on the same Line, which is painted in the unread color; other Lines and the alerts unchanged |
| Approval clears red | None | `approve`: PostToolUse for task-1's shell wait | `reference` | `approval-clears-red`: task-1 listed working on the same Line, painted in the working color; the blocked alert gone |
| Approval requested | None | `request-approval`: PermissionRequest for task-4 | `reference` | `approval-requested`: task-4 listed blocked on the same Line, painted in the blocked color; alerts `2 blocked` and `1 question` |
| Task resumes | None | `resume`: UserPromptSubmit for task-3's next turn | `reference` | `task-resumes`: task-3 listed working on the same Line, painted in the working color; alerts unchanged |
| Project layout (configuration) | Options, Project; select two free Lines; Reserved for | None | `reference` | `project-layout`: Project style, both Lines reserved for Notification Service with no pending edit, each project half painted in the project color |
| Lighting modes and animation | Work, Quiet, Free; Options, Replay | None | `reference` | `lighting-modes`: Work advances the light phase on active Lines, Quiet holds it, Free notes the release and disables Locate, Work resumes, Replay finishes; with reduced motion Work holds still and Replay does not animate; the Light Panels keep their own mode |
| Light Panels | Device, Light Panels; Quiet | None | `reference` | `panels-view`: every triangle drawn, each placed task's triangle filled with its status color, Quiet on the Panels leaves the Lines in Work |
| Device boundary | Open the map | None | `layout-unavailable` | `device-read-refused`: the map's layout-unavailable notice, a refused `GET` light request to `192.0.2.1` from startup in the boundary log, and during the step no attempt other than the map's own bounded layout retries |
| Hub-fed lifecycle state | Open the map | None; the paired Hub's own sessions | `hub-paired` | `hub-lifecycle-painted`: the wall is current at the revision the Hub serves; each session from the paired source is listed with the status, title and evidence the feed gives, and paints its Line in that status's color; nothing from another source is shown; during the step only allowed connections to the paired Hub's port |

Every check throws on a mismatch or returns `true`; the plug-in wraps each step so that a check returning `false`, or any other value such as a count, fails the capture. In each transition step, every other Line keeps its colors. Every step also asserts that the page requested only its own run origin and that the run recorded no device attempt during the step. The page's content security policy already blocks cross-origin subresources, so the origin check guards navigation and policy regressions. `device-read-refused` instead accepts during the step only the map's bounded layout retries, at most two, each made on the first poll 10 s or more after the previous read. It checks that bound from the recorded times: at most three layout reads since the seed, each at least 9 s after the previous one. A recorded time trails the map's decision by however long the read takes to start, which a pause or slow I/O can stretch, so the check leaves about a second of slack. A map that reads on every 1 s poll still fails the spacing, and one without the three-read limit fails the count. It also requires the startup read to have been refused. Every capture, including a failed one, attaches its step's boundary record, `device-boundary.json`.

Negative controls are ordinary capture steps that apply a known-wrong result to the same assertions. Each reports `failed` at the named assertion, and the checks below require that. The verified set must hold only passing captures, because the Hub's delivery preflight rejects a receipt whose verified set contains a failed one. For proof that a delivery cites, capture the reference steps, run `handoff`, and only then capture the controls, which land in `after-handoff/` and still read `failed`:

| Control | Known-wrong result | Failing assertion |
| --- | --- | --- |
| `control-stale-completion` | Stop for an earlier turn, which the hook handler ignores | task-0 reads unread in the task list |
| `control-unread-painted-working` | The page served with unread Lines painted in the working color | task-0's Line is painted in the unread color |
| `control-stale-red` | PostToolUse for another tool, which leaves task-1's approval waiting | task-1 reads working in the task list |
| `control-device-attempt` | A completion whose worker stand-in also tries to send the effect to each device | no device attempt was recorded during the step |
| `control-paired-installed-port` | In `hub-paired`, the stand-in polls the installed Hub's port 8788 through the real shared-input transport | only the paired Hub feed was contacted during the step |
| `control-paired-light-request` | In `hub-paired`, the stand-in also tries to send the effect to each device | only the paired Hub feed was contacted during the step |

Checks:

- `python3 scripts/check.py` makes real attempts through the Nanoleaf transport, the worker launcher, a loopback service, a geometry read that bypasses the seam, a multiprocessing spawn, ctypes library loads and symbol lookups, and, on Python 3.14, a ctypes call through a function resolved before the guard and a subinterpreter. Each is refused. Unguarded control processes do reach the loopback service by each of those paths, so the check can observe a leak. It also covers seeding, the directory refusals with exit status 2, driving, serving, relaunch on the recorded port and two independent runs. For `hub-paired` it covers the seed and its refusals, the paired boundary, a run against a stand-in Hub feed and controller caller, a Hub that refuses at first, a relaunch on the recorded controller port, a controller port already in use, a controller listener that stops, the page's Hub link and the paired defect transitions. A positive control shows that the test backstop records and refuses what a boundary that allows everything lets through. It also pins the vendored core archive against its checksum, receipt and manifest, and tests `controller_server.register()`.
- `npm run test:verify` needs no systemd. It launches each scenario directly and checks readiness, the probe and the boundary check, including its layout-read bound. It checks that a failed seed names its cause without the command or any path. It serves `tests/fixtures/eager_layout_map.py`, a map that reads its layout on every poll, and requires both `device-read-refused` and the boundary check to fail for it. It then runs every capture step through the core's `runCaptureStep`. Reference steps must pass with a screenshot and a finalized video, and each control must fail at its named assertion. `hub-paired` runs pair with a stand-in Hub feed served by the test from `tests/fixtures/paired-hub-feed.json`. A stand-in controller caller presents the Hub's token to the controller API. The tests cover a Hub that refuses and then accepts, a pairing that never comes up within 30 s, a feed that goes stale or moves to another owner, a brief Hub outage during a capture, a session left without a Line, a credential file that is not private, and a relaunch that keeps the controller port. They also check the installed core file for file against its manifest. Output goes to ignored `test-results/verify/`.
- `npm run test:verify:lifecycle` runs the supervised lifecycle with real transient user units, using a unique app name and private roots. It covers the receipt and build identity, doctor, fresh capture, handoff with frozen proof and a post-handoff capture, extend, stop, two concurrent runs, a start that attempts a device request, a seed that fails without leaking a path, a start that exits early, an interrupted start, lease expiry, and restart, including a restart of an expired run whose frozen proof stays unchanged. It also pairs a run with a stand-in Hub, captures `hub-lifecycle-painted`, reseeds it standalone, and reseeds one without its credential files. Without a user manager it skips with the reason printed; `APP_VERIFY_REQUIRE_SYSTEMD=1` makes that a failure.

Not covered by a run:

- Physical color, brightness, frames and timing. The stand-in never renders, so a run proves no device output.
- Completion comets, outward waves and Locate flashes. They are queued in state, but the stand-in never plays them; the map shows status colors. The animation preview is [#156](https://github.com/jimmie-potts/codex-nanoleaf/issues/156).
- `GET /api/rendering` reports pending or unknown output, because no worker sends.
- Configuration through the page is limited to one representative action, the Project layout reservation. Outside `hub-paired`, configuration through the controller API or shared input is not exercised; MCP never is. Scenes, native brightness overrides, requested animations and the Codex metadata reader do not run.
- Layout discovery and device enrollment.
- Outside `hub-paired`, the header's B.U.N.N.Y. link opens the installed Hub dashboard, outside the run. A `hub-paired` run points it at the paired Hub run instead; see [Hub-paired runs](#hub-paired-runs).
- A reseed relaunches the server with a new edit token. Reload a preview tab opened before the reseed before editing.
- An expired run cannot hand off again: `handoff` reports `run-not-running` and leaves its proof untouched. `restart` starts a new run from it, with the original lease length.
- Windows browser access to a preview is qualified under Hub [#497](https://github.com/jimmie-potts/agent-device-hub/issues/497); `doctor` only checks HTTP reachability with Windows `curl.exe`.

### Hub-paired runs

The `hub-paired` scenario ([#194](https://github.com/jimmie-potts/codex-nanoleaf/issues/194)) makes a run a consumer of a paired Hub run for the integrated preview of Hub [#495](https://github.com/jimmie-potts/agent-device-hub/issues/495). The Hub run remains the only agent-state owner. The wall follows its feed and serves the controller API the Hub calls. The pairing convention, shared with Pixoo's [#120](https://github.com/jimmie-potts/divoom-app-upgrade/issues/120):

| Item | Value |
| --- | --- |
| Run input `hub-feed` | The Hub run's origin, exactly `http://127.0.0.1:<port>/`, never an installed service's port. The wall polls `<hub-feed>api/monitor/v1/sessions?snapshotVersion=1.2` about once per second |
| Credential files, in the run's runtime directory (`<state root>/<run-id>/`) | `hub-feed-token`: the bearer token the wall presents to the Hub's feed. `hub-controller-token`: the token the Hub presents to the wall's controller API. Each holds one 43-character base64url token, mode 0600, owned by the user, not a symlink |
| Shared input | Owner `verify-owner`, consumer `nanoleaf`, the one qualified source `{provider: codex, client: cli, hostId: verify-host, sourceId: verify-source}`, no acknowledgment credential |
| Controller | Identity `wall-controller`, device `wall`, source `wall`. The Hub's token is accepted as principal `hub` with read and control scopes, stored only as its SHA-256 digest. Only the Lines are on the controller |
| Endpoint `controller` | `http://127.0.0.1:<port>/`, the wall's real controller listener. Configure the Hub with `<endpoint>controller/v1`; the integration extension is at `<endpoint>controller/integration/v1` |

Neither token is ever an argument, environment variable, input, receipt field, event, log line or attachment. A seed without a usable file fails with a fixed line such as `demo.py seed failed: hub-paired needs a private hub-feed-token file in the run directory`.

The order the orchestrator uses:

1. `start` the wall standalone.
2. The Hub run starts.
3. Write both credential files into the wall run's runtime directory.
4. `npm run -s verify -- scenario <run-id> hub-paired --input hub-feed=http://127.0.0.1:<hub port>/`. The result names the `controller` endpoint.
5. Configure the Hub run to accept the feed token and call the controller endpoint.

`start --scenario hub-paired` cannot work, because `start` creates the runtime directory. A `hub-paired` reseed before the files exist fails, and the core then stops the run. `restart` of a paired run starts a new runtime directory without the files, so pair a new run instead.

In `hub-paired`:

- The seed selects shared input without the preflight read that `shared-select shared` makes, because the seed's boundary allows no connection and the Hub may accept the credential only later. The Poller checks every snapshot as the preflight would.
- `serve` runs the real controller listener in a thread; port 0 takes a free port that no installed service uses. If the listener stops after it was announced, the run prints `controller listener stopped` and exits with status 1, so the unit fails visibly. `serve` also runs a worker stand-in thread. About once per second, and when the map or the controller API wakes it, the stand-in polls the feed through the real `shared_source.Poller` and applies the Lines' integration settings queue, pending edits and allocation. It never renders or sends.
- The boundary of `serve` and `drive` allows a TCP connection to `127.0.0.1` on the paired Hub's port and records each one as `allowed`, with the address the process asked for. Datagrams, other ports and hosts, installed ports, processes and every light request stay refused. `seed` allows nothing.
- A Hub that rejects the feed token or does not answer leaves the run serving. The feed reads `unavailable` before the first snapshot and `stale` after one, tasks stay steady with uncertain evidence, and the Poller retries each second.
- Until the wall has accepted a snapshot since the seed, the `paired-feed` check is `skipped` for 30 s after the seed, so the reseed in step 4 passes before step 5 happens. After that it is `failed` with the feed's error code, such as `feed-rejected`, `feed-unavailable` or `invalid-feed`: the pairing never came up. Once the wall has a snapshot, the check reads the Hub with the wall's feed token and passes only when the feed is current and the wall's revision equals the one the Hub serves. It fails when that does not hold within about 3 s. It is `skipped` in every other scenario.
- Once a run has announced the `controller` endpoint, every later scenario announces it again on the same port, as the core requires. A standalone scenario serves it with no accepted credential, so the Hub's calls are unauthenticated there.
- The page's header link to B.U.N.N.Y. leads to the paired Hub run's origin, the `hub-feed` input, instead of the installed Hub at `http://127.0.0.1:8788/`, so no link in the integrated preview leaves the runs. The run's server substitutes that one `href` when it serves `/`. `bridge/wall.html` and the installed map are unchanged, and the page looks the same. If the page does not hold the installed link exactly once, the server answers 503 rather than serve the installed link. The run's artifact digest hashes the files on disk, so the substitution does not change it.

Every run serves a read-only `GET /verify/state` on its map origin for scripted assertions. It needs no credential; the `Host` must be `127.0.0.1:<port>`, as on every map route:

```json
{"apiVersion": "wall-verify/1", "scenario": "hub-paired",
 "feed": {"source": "shared", "connection": "current", "revision": 7, "receivedAt": 1790517293.33, "ownerId": "verify-owner", "error": null},
 "integration": {"applied": 1, "queued": 0, "failed": 0}}
```

`feed.connection` is `current` only while the last accepted snapshot is at most 4 s old, `stale` after that and `unavailable` before the first. `feed.revision` is the snapshot revision last applied, and `feed.ownerId` the owner of that snapshot; both are `null` before the first accepted snapshot. The wall accepts only `verify-owner`'s snapshots, so `ownerId` is `verify-owner` or `null`, never the configured value reported without evidence. `feed.error` is the last poll's fixed error code. `integration` counts the Lines' integration settings requests: `applied` by the stand-in, `queued`, and `failed` for any other outcome. The ledger keeps the last 256 completed requests. The route never reports a token or a token path.

Not covered in `hub-paired`: the Hub's controller v1 commands are admitted and journaled but never executed, because the stand-in never runs the device writer and the light transport stays refused. After 30 s the listener fails them as `transport-failure` and holds the device. Comets and animation, acknowledgment and restarting one consumer while the pairing continues are also not covered.

Tests run `hub-paired` beneath `tests/fixtures/backstop_demo.py`. It adds a second audit hook after the boundary that records and refuses anything the boundary let through except the paired port, so a boundary regression cannot reach an installed service. A positive control in `tests/test_demo_runs.py` replaces the boundary's rule with allow-all and requires the backstop to record and refuse the leak. The boundary's own `refused` record, not an empty backstop log, is the evidence that a connection was refused. Every capture's log names the demo entry that served and drove it, such as `demo entry: tests/fixtures/backstop_demo.py`.

To make a delivery evidence run for a `hub-paired` change, run `node tests/fixtures/paired-evidence.mjs <record directory>` from a clean checkout on the default roots. It:

1. Starts a run and captures the standalone reference steps.
2. Writes the credential files and pairs the run with a stand-in Hub feed (`tests/fixtures/stand-in-hub.mjs`).
3. Makes the Hub's controller calls (`tests/fixtures/controller-caller.mjs`) and captures `hub-lifecycle-painted`.
4. Hands off with a reset and captures every control after handoff; `control-paired-installed-port` runs through `tests/fixtures/backstop-verify.mjs`, beneath the backstop.
5. Reseeds `reference`, scans every record for the tokens and stops the run.

`summary.txt` in the record directory lists each operation's own exit code.

### Aggregate reset pause

An explicitly launched disposable `hub-paired` wall can pause its Hub feed while the owner resets. The adapter passes `--feed-pause-runtime <runtime-dir> --feed-pause-run <run-id>` to the demo; ordinary launches do not enable these controls. In the existing private runtime directory, `feed-pause.request` and `feed-pause.release` contain exactly `{version:1,runId,nonce}`. The nonce is 32 lowercase hexadecimal characters. Controls must be owned, private regular files of at most 4 KiB, with no links.

The paired writer stops admitting Hub reads and finishes its active read before atomically writing mode-0600 `feed-pause.ack`, containing the request fields and its positive integer `pid`. The page, health route and inbound controller work remain available, and retained feed state ages normally. This paired configuration has no outbound Hub command path. Invalid requests block polling and withdraw an existing acknowledgment. Removing the request resumes the same process. A release file alone has no effect on a running process.

After the Hub owner is ready again, the coordinator writes a matching release and reseeds the wall `hub-paired`. The core stops the old process before seed. Seed refuses an outstanding pause without matching authorization, or a change to another scenario; after fresh state is successfully written, it atomically claims and validates the matching controls, then deletes only the claimed files. A concurrent newer request stays in place; a changed claim is restored without overwriting another control. The replacement can then accept the owner's lower new revision. Successful reseeding preserves token files and recorded ports. Seed refuses missing or changed authorization without resuming polling. The core cleans the runtime of an already stopped failed run, including retained private claims; the run remains stoppable and frozen proof stays unchanged.

The `paired-feed` diagnostic skips a valid pause and fails an invalid request or release before probing the Hub. A release must match the current request. Avoid concurrent individual `doctor`, capture or scenario commands during aggregate pause: the coordinator serializes aggregate mutations, and an already active independent diagnostic is outside the serving process's drain acknowledgment. After release, require the feed check to pass. These controls do not apply to installed Nanoleaf or physical devices.

The Python and verification suites exercise held reads, invalid controls, release refusal, nonce changes, lower revision recovery and ordinary-launch isolation. The `paused paired run` case in `npm run test:verify:lifecycle` additionally captures real browser proof, checks that the old unit is stopped inside the seed callback, and verifies frozen proof after reset and failed release. Run it with `APP_VERIFY_REQUIRE_SYSTEMD=1` on the owner host; a skipped result is not systemd qualification.

## Hosted CI

Depot CI runs the workflow in `.depot/workflows/ci.yml` on pull requests and pushes to `main`. It reports each job as a GitHub check. A newer PR revision cancels the superseded PR run, and each `main` revision runs independently. Each job has a ten-minute timeout. Depot CI provides only Linux sandboxes, so normal CI has five Linux jobs:

| Check | Coverage |
| --- | --- |
| Workflow checks | `npm run check:workflow` and `npm run test:workflow` with Node 24 |
| Python 3.12 and Python 3.14 | Controller dependencies and `python scripts/check.py` with Node 24 available |
| Wall map browser checks | Controller dependencies for the paired run, Prism tests, a clean Prism export, `npm run test:browser`, `npm run test:verify` and `npm run test:verify:lifecycle` in Chromium; the lifecycle checks skip, printing the reason, when the runner has no systemd user manager. Screenshots, verification videos and assertion logs are uploaded as the `prism-wall-review` artifact with a requested 14-day retention |
| MCP source checks | `npm run test:mcp` |

`.github/workflows/ci.yml` stays in the repository as the migration source. It is disabled in GitHub Actions. Its runs, including earlier billing-blocked failures, are not evidence for a candidate.

## Workflow tooling

Run `npm ci` to install the locked development dependencies. Use npm's default
cache (`~/.npm` on Linux and WSL), not a cache under `/tmp`; `/tmp` can be a
small RAM-backed filesystem shared by every session. If a sandbox makes the
default cache read-only, report that instead of redirecting it. The bridge uses
the standard library; controller tests also require the pinned
`requirements-controller.txt` dependencies.

`npm run openspec -- <arguments>` uses the pinned OpenSpec 1.12.0 CLI. The wrapper
disables telemetry and completion/animation prompts through child-process
environment variables. Each invocation uses a temporary CLI configuration
directory and a separate temporary Codex home, which are removed afterward.
This prevents OpenSpec's initialization migration from changing user settings
or deleting global legacy Codex prompts, even when `--profile core` is supplied.
Global CLI preferences do not apply through this wrapper, and CLI configuration
changes made through it do not persist. Put repository rules in
`openspec/config.yaml`. The wrapper preserves the caller's working directory so
isolated fixtures can use their own planning root. Normal repository work runs
from the assigned worktree root.

Run `npm run check:workflow` after workflow, skill, or OpenSpec changes. It invokes
strict non-interactive validation separately for current specs/changes and for
archived task completion. Either failure makes the command fail. Zero items is
a valid bootstrap result and is reported as zero, not as a reviewed baseline.
These CLI checks validate syntax and archive task markers; they do not replace
acceptance tests, artifact-completeness checks, or independent review.

Run `npm run test:workflow` to exercise empty, valid, invalid, and incomplete
archive fixtures and regeneration without user-configuration changes. Depot CI runs
both commands in the always-running Workflow checks job, alongside the existing
product checks.

Initialize specification storage, if needed, with:

```bash
npm run openspec -- init --tools none --profile core --no-animation
```

The project-scoped core profile override and `--tools none` keep skill
integrations out of this repository. OpenSpec's schema and CLI remain pinned
here; its reusable skill instructions are maintained in the shared catalog.

## Shared skills

The canonical source is [agent-skills](https://github.com/jimmie-potts/agent-skills).
Use a reviewed checkout of that repository. From its root, install the selected
personal skills using its existing manager:

```bash
./scripts/manage-skills.sh install --agent both plan-work deliver-work tdd grill-with-docs grilling domain-modeling code-review openspec-propose openspec-explore openspec-apply-change openspec-update-change openspec-sync-specs openspec-archive-change unslop
./scripts/manage-skills.sh status --agent both
```

Personal provisioning requires an explicit request; source delivery documents
these commands without running them against personal directories. Use `--agent
codex` or `--agent claude` to provision only one tool. The manager links skills
under `~/.agents/skills` for Codex and `~/.claude/skills` for Claude. It preserves
conflicts, so inspect its output and resolve ownership before replacing links.
Keep that reviewed checkout available. Restart the target tool to verify fresh
discovery. TDD and Grill with Docs retain their global explicit-only settings;
Nanoleaf's agent instructions deliberately compose them within authorized work.
That routing is separate from host discovery. A missing skill must be installed
or reported, without creating a local copy as a fallback.

For Claude's instruction and skill discovery checks, see
[Claude Code setup](claude-code.md). The manager's status verifies filesystem
links; it does not establish that a running host loaded their contents. In
Codex Desktop, verify the required skills in a fresh task's available skill
catalog. When testing outside personal setup, the manager accepts
`CODEX_SKILLS_DIR` and `CLAUDE_SKILLS_DIR` pointing to temporary destinations.
Those variables configure the manager, not the hosts' discovery paths.

This repository keeps Nanoleaf policy and contracts, with no shared skill
copies or external symlinks. Create a local skill only for a procedure that
depends on the Nanoleaf domain. Do not regenerate `openspec-*` integrations here.
Update shared skill definitions and their generator provenance in `agent-skills`.

For a fresh or cloud environment, provision the reviewed shared catalog outside
this repository using the host's supported skill setup. The local symlink setup
does not prove cloud availability. Record the evaluated shared-catalog revision
and actual loaded source paths in PR validation evidence.

Validate authored skills with the catalog's checks and the skill-creator
validator. Exercise shared routing, authority boundaries, TDD, and delivery with
independent agents in isolated fixtures. Record observed actions and limitations;
a schema pass alone does not prove correct selection. Keep exercise artifacts
outside product Git history and summarize their evidence in the PR.

## Upgrade the installed integration

Use the owning [upgrade and rollback procedure](linux-install.md#upgrade-and-roll-back-the-installed-runtime). The Python suite covers receipt semantics, admission, source provenance, component adoption and recovery with isolated state and fake services. Run `python3 scripts/qualify-upgrade.py --scratch <disk-backed-scratch> --evidence <private-evidence>` under Node 24 to build and qualify the exact committed artifact; CI runs it on Python 3.14. This requires the pinned controller dependencies and npm and does not inspect an installation. Keep the emitted source/archive/manifest hashes with delivery evidence. A bare `bridge.py setup` is refused; `setup --reset` clears task records and is never an upgrade step.

For physical checks, hold the installed worker lock before sending isolated test effects. Hook-triggered workers can restart during testing, so verify lock ownership. Keep test tasks and scene choices in temporary state, then restore the latest real mode, layout, tasks, and scene preference before releasing the lock. Record controller readback separately from human confirmation of physical orientation.

## Current portability limits

The runtime is a personal Linux integration on WSL. The Windows tray, PowerShell installer and WSL-to-Windows forwarding were retired in [ADR 0012](decisions/0012-retire-windows-runtime.md). The Codex metadata reader uses current desktop JSON fields that may change in future releases and reads them from the mounted Codex Desktop home read-only.

The geometry fixture retains the tested arrangement with arbitrary panel IDs. It contains no controller credentials or task metadata. Actual panel IDs and saved project reservations remain in the installation.

## Source import evidence

The starting implementation passed 100 tests in WSL and, at the time, Windows. Prior physical readback covered split zones, overflow, both animation coverage choices, deferred comet edits, Quiet Locate, and scene restoration. Those historical results are context for the import. CI and new local runs provide evidence for later commits.

## Optional controller development

For controller API fixtures, install the pinned source dependencies with `python -m pip install -r requirements-controller.txt`, then run the normal Python suite. The listener imports the verified shared Python consumer; legacy commands remain usable without these packages. Run the existing browser and workflow checks for API/OPSX changes. See [the controller guide](controller-api.md) for the immutable release receipt, source-only activation commands and separate installation/physical acceptance boundary.

## Desktop retirement consumer

The normal Python suite includes snapshot 1.1 validation and a missed-retirement regression that reopens saved state, resets one task's manual project and effects, preserves its peer, and distinguishes healthy empty recovery from feed loss. Run `fnm exec --using=24 -- python3 scripts/check.py` with the controller dependencies installed. Browser and workflow checks remain required for this shared-input change.

The owning [Hub #218](https://github.com/jimmie-potts/agent-device-hub/issues/218) consumer harness also passes real owner snapshots and the shared 1.1 fixture corpus through this candidate. Record the exact source revisions in the PR. This evidence does not install the consumer or qualify a device.

The shared-input suite also verifies read-to-idle Line retention and device-local
eviction through restart, feed recovery and fresh turns/generations. HTTP checks
exercise origin/edit-token rejection and stale controls. Browser checks cover
the Evict button, keyboard focus, failed requests, idle animation and narrow
layout. Run `python3 scripts/check.py` and `npm run test:browser`; these use
synthetic tasks and do not evict an installed task. Changed UI needs renewed
human approval before merge.
