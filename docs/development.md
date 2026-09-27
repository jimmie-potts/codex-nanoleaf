# Development and deployment

The repository is the canonical source. Fresh Linux setup and service operation follow [the Linux installation guide](linux-install.md); its private runtime lives under `~/.local/share/codex-nanoleaf`. The retired Windows installation and the original scratch workspace are historical and are not used for future changes.

Follow [the SDLC guide](sdlc.md) for issue scope, planning, TDD, independent review,
and merge criteria. It also defines when installation is part of a task.

## Validate a change

Run `python3 scripts/check.py` from the root. Install the optional controller dependencies first with `python3 -m pip install -r requirements-controller.txt`, preferably in an isolated virtual environment. They exercise status transitions, read handling, comets, scenes, modes, project placement, split rendering, metadata recovery, and local HTTP validation. A successful run contacts neither a controller nor the real Codex state.

Run `npm run test:browser` after map or API changes. It starts the synthetic demo on an available loopback port and shuts it down afterward. Screenshots are written to ignored `test-results/`. To inspect the map manually, run `python3 scripts/demo.py` and open its printed URL.

Exercise Linux installation and device enrollment with isolated state and fake device transport; never enroll a personal device from a development checkout. `cd tests && python3 -m unittest test_enrollment` runs the focused enrollment tests; the operator commands are in [the Linux installation guide](linux-install.md#add-nl22-light-panels). Hosted CI runs the Python, browser, MCP and workflow checks on Linux; there are no platform-specific checks.

## Verification runs

A verification run serves the actual wall server over its own synthetic state so an agent can exercise a change, keep assertion-backed proof and hand over a disposable preview. The shared lifecycle core from the Hub ([app verification contract](https://github.com/jimmie-potts/agent-device-hub/blob/main/docs/app-verification.md)) owns the run's supervisor unit, lease, receipt, proof and preview card. This repository supplies the wall plug-in in `scripts/verify/`, built on these `scripts/demo.py` commands:

| Command | Effect |
| --- | --- |
| `python3 scripts/demo.py scenarios` | Print the scenario names and descriptions as JSON |
| `python3 scripts/demo.py seed --state-dir <dir> --scenario <name>` | Write a scenario into an empty directory: registry, layout, projects, tasks and hook waits |
| `python3 scripts/demo.py serve --state-dir <dir> --port 0` | Start the wall server as the installed map starts, on `127.0.0.1`. It writes `map-server.json` and prints one ready line, `{"url": …, "instance": …}`. The page's edit token is never printed |
| `python3 scripts/demo.py drive --state-dir <dir> <transition>` | Apply a named task transition through the actual hook handler, then the worker stand-in |

Every command first installs a process boundary. It refuses outbound socket connections, datagram sends and new processes, and it routes the wall server's light-request seam to a trap. Each refusal is appended to `<dir>/device-boundary.jsonl` with its kind, target and time, never a credential. The wall server sees a refused request as an unreachable device.

Two checks prove the boundary and the steps:

- `python3 scripts/check.py` makes real attempts through the Nanoleaf transport, the worker launcher, a loopback service and a geometry read that bypasses the seam. Each is refused. An unguarded control process does reach the loopback service, so the check can observe a leak.
- `npm run test:verify` serves one run per capture step. Every reference step must pass and every negative control must fail at its named assertion. It writes screenshots, videos and assertion logs to ignored `test-results/verify/`.

In a run, the wall server, map page, private SQLite state, hook handler and allocation are actual code. The light worker is a stand-in that applies edits and allocation and never renders or sends. The Lines (`192.0.2.1`) and Light Panels (`192.0.2.2`) are fixture layouts behind the boundary, and projects and tasks are synthetic. A run never reads Codex state, the installed runtime or its ports.

Scenarios:

- `reference`: the browser suite's fixture. Five tasks in all four statuses across three projects, on Lines and Light Panels in Work.
- `empty`: the same devices with no tasks.
- `layout-unavailable`: the reference tasks without saved drawing geometry. The map's startup asks the Lines for their layout, and the boundary refuses it.

Capture steps change the run's state, so run each step on a freshly seeded run.

| Behavior | Page entry | Driver action | Scenario | Capture step and expected observation |
| --- | --- | --- | --- | --- |
| Lines wall and task list | Open the map | None | `reference` | `wall-ready`: 15 Lines; each task listed with its status; alerts `1 blocked` and `1 question`; Device offers Lines and Light Panels; each placed task's Line painted in its status color |
| Task completion | None | `complete`: Stop for task-0 | `reference` | `task-completes`: task-0 listed unread on the same Line, which is painted in the unread color; other Lines and the alerts unchanged |
| Approval clears red | None | `approve`: PostToolUse for task-1's shell wait | `reference` | `approval-clears-red`: task-1 listed working, the blocked alert gone, its Line painted in the working color |
| Project layout (configuration) | Options, Project; select two free Lines; Reserved for | None | `reference` | `project-layout`: Project style, both Lines reserved for Notification Service with no pending edit, each project half painted in the project color |
| Lighting modes and animation | Work, Quiet, Free; Options, Replay | None | `reference` | `lighting-modes`: Work advances the light phase on active Lines, Quiet holds it, Free notes the release and disables Locate, Work resumes, Replay finishes, the Light Panels keep their own mode |
| Light Panels | Device, Light Panels; Quiet | None | `reference` | `panels-view`: every triangle drawn, each placed task's triangle filled with its status color, Quiet on the Panels leaves the Lines in Work |
| Device boundary | Open the map | None | `layout-unavailable` | `device-read-refused`: the map's layout-unavailable notice, and a refused `GET` light request to `192.0.2.1` in the boundary log |

Every step also asserts that the page requested only its own run origin and that the run recorded no device attempt; `device-read-refused` instead requires its attempt to be refused. The `request-approval` and `resume` transitions are available for new steps.

Negative controls use the same assertions against a known-wrong result, and each must fail at the named assertion:

| Control | Known-wrong result | Failing assertion |
| --- | --- | --- |
| `control-stale-completion` | Stop for an earlier turn, which the hook handler ignores | task-0 reads unread in the task list |
| `control-unread-painted-working` | The page served with unread Lines painted in the working color | task-0's Line is painted in the unread color |
| `control-stale-red` | PostToolUse for another tool, which leaves task-1's approval waiting | task-1 reads working in the task list |

Not covered by a run:

- Physical color, brightness, frames and timing. The stand-in never renders, so a run proves no device output.
- Completion comets, outward waves and Locate flashes. They are queued in state but never played; the map shows status colors. The animation preview is [#156](https://github.com/jimmie-potts/codex-nanoleaf/issues/156).
- `GET /api/rendering` reports pending or unknown output, because no worker sends.
- Scenes, native brightness overrides, requested animations, the controller API, MCP, shared input and the Codex metadata reader. None of them run.
- Layout discovery and device enrollment.
- The header's B.U.N.N.Y. link opens the installed Hub dashboard, outside the run.
- A reseed relaunches the server with a new edit token. Reload a preview tab opened before the reseed before editing.

## Hosted CI

Depot CI runs the workflow in `.depot/workflows/ci.yml` on pull requests and pushes to `main`. It reports each job as a GitHub check. A newer PR revision cancels the superseded PR run, and each `main` revision runs independently. Each job has a ten-minute timeout. Depot CI provides only Linux sandboxes, so normal CI has five Linux jobs:

| Check | Coverage |
| --- | --- |
| Workflow checks | `npm run check:workflow` and `npm run test:workflow` with Node 24 |
| Python 3.12 and Python 3.14 | Controller dependencies and `python scripts/check.py` with Node 24 available |
| Wall map browser checks | Prism tests, a clean Prism export, `npm run test:browser` and `npm run test:verify` in Chromium; screenshots, verification videos and assertion logs uploaded as the `prism-wall-review` artifact with a requested 14-day retention |
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

The Linux installer has no upgrade or rollback mechanism; [the Linux installation guide](linux-install.md) describes preparing a fresh installation and the operator's own retention of the current state directory. A bare `bridge.py setup` is refused and points at the Linux installer. `setup --reset` clears task records and is never an upgrade step; `setup --refresh` only redraws existing task state.

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
