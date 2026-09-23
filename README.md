# Codex Nanoleaf

Turn Nanoleaf Lines into status indicators for Codex Desktop tasks. A local wall map lets you assign project colors and reserve Lines for each project.

- Work mode shows two-second task pulses, status waves, and completion comets.
- Free mode leaves lighting control to Nanoleaf. Quiet uses steady indicators at 10%.
- Classic layout assigns tasks automatically with whole-Line colors.
- Project layout uses a steady project half and a task-status half, with Shared overflow.
- The wall map supports multi-selection, color picking, half swapping, Locate, and rotation, in a neon HUD style that pulses active Lines on screen in Work and dims the wall in Free.

The integration supports a fresh Linux installation with separate Python services and a Node MCP host. Hooks, the map, controller, and worker coordinate through private Linux SQLite. The existing worker remains the sole light writer. Legacy Windows installations retain their Windows Python forwarding. Tests and the demo run without lights or credentials.

## Development

For planning, TDD, review, and delivery, follow [the development workflow](docs/sdlc.md).
GitHub issues track requested work; each deliverable normally uses an isolated
worktree and one PR. Repository instructions select the relevant shared workflow automatically.

Use Python 3.12 or newer. From the repository root:

```bash
python3 scripts/check.py
python3 scripts/demo.py
```

On Windows, use `python` instead of `python3`. Open the URL printed by the demo, normally `http://127.0.0.1:8765`. Its project names and tasks are synthetic; changes affect only the temporary demo state.

For browser checks, use Node.js 22 or newer:

```bash
npm ci
npx playwright install chromium
npm run test:browser
```

On a fresh Linux machine, Playwright may also need its browser system dependencies. The CI workflow uses `npx playwright install --with-deps chromium`. `PYTHON` can select a Python executable; `NANOLEAF_BROWSER_EXECUTABLE` can select an existing Chromium-based browser.

[Depot CI](docs/development.md#hosted-ci) runs workflow checks, the Python suite with Python 3.12 and 3.14, browser checks, and MCP source checks on Linux. Depot CI has no Windows sandboxes, so Windows checks run locally.

After `npm ci`, run `npm run check:workflow` to validate OpenSpec work and
`npm run test:workflow` to exercise the validation commands. OpenSpec 1.12.0 is
pinned locally; use `npm run openspec -- <arguments>` instead of a global CLI.
Reusable skills come from the [shared catalog](https://github.com/jimmie-potts/agent-skills); see [setup](docs/development.md#shared-skills). This repository keeps no shared skill copies.
The [wall Line identification specification](openspec/specs/wall-line-identification/spec.md)
owns numbering, selection, and the Locate boundary. The
[device state specification](openspec/specs/device-state/spec.md) owns the
device registry, device-scoped state, the per-device layout shape and the
Linux migration. Other behavior remains
documented in [the bridge guide](bridge/README.md) until migrated through review.

## Installation

For a fresh Linux or WSL installation, follow [the Linux setup guide](docs/linux-install.md). It uses Python 3.12 or newer with venv support and native Node 24/npm, generates three user systemd services, and prints the wall URL at `http://127.0.0.1:8765`. It imports no old project data. The operator stops this project's Windows owner before activating Linux hooks or services.

The following instructions apply to legacy Windows installations.

For an existing installation, run `bridge/install-modes.ps1` in Windows PowerShell. It backs up the program and private state, then restarts only this installation's worker, map server, and tray. A source checkout does not change the running installation.

For fresh setup, follow [the integration guide](bridge/README.md). This version retains the original machine's private controller IP as the setup default and expects Codex's bundled Windows Python runtime. It is a personal integration, not a general-purpose installer. See [development and deployment](docs/development.md) for the WSL workflow and limitations.

## Codex

Add this repository folder as a WSL project in Codex Desktop. The root [AGENTS.md](AGENTS.md) describes validation, state preservation, and runtime boundaries. [Codex setup notes](.codex/README.md) list test and demo commands for optional toolbar actions.

## Claude Code

Claude Code CLI in WSL can use the same source repository. [CLAUDE.md](CLAUDE.md)
imports the shared project instructions. Follow [Claude setup](docs/claude-code.md)
for prerequisites, shared skills, and launch commands. Concurrent Claude and
Codex work uses a separate branch and worktree for each deliverable.

## Repository contents

| Location | Purpose |
| --- | --- |
| `bridge/` | Deployable Python bridge, local map, and Windows scripts |
| `tests/` | Isolated regression tests and browser checks |
| `tests/fixtures/` | Geometry fixture with substituted panel IDs |
| `scripts/` | Test runner and device-free demo |
| `.depot/` | Depot CI workflow |
| `.github/` | Pull request and issue templates; disabled GitHub Actions source workflow |

Credentials, hook configuration, live databases, task metadata, scene preferences, screenshots, and installation backups are excluded from Git. No live state is required to run the tests.


## Shared monitoring direction

[The hub integration plan](docs/hub-integration.md) records shared contracts,
the [shared session consumer](docs/shared-input.md) and a future unified overview. Shared monitoring remains separate from the Linux runtime port. Source changes
do not update the current installation. GitHub issues own the migration prerequisites.

The optional [local MCP host](docs/local-mcp.md) supports Windows and WSL through the protected controller. Source delivery and separately authorized installed-client/light acceptance remain distinct.

## Cross-project work guide

The [hub work guide](https://github.com/jimmie-potts/agent-device-hub/blob/main/docs/work-guide/README.md) contains the shared remaining-work
map, delivery history and architecture diagrams as a dated snapshot. A change
here needs a linked hub PR only when its task intentionally updates the guide;
see [the SDLC](docs/sdlc.md#cross-project-work-guide).
