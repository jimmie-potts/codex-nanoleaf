# Codex Nanoleaf

Turn Nanoleaf Lines into status indicators for Codex Desktop tasks. A local wall map lets you assign project colors and reserve Lines for each project.

- Work mode shows two-second task pulses, status waves, and completion comets.
- Free mode leaves lighting control to Nanoleaf. Quiet uses steady indicators at 10%.
- Classic layout assigns tasks automatically with whole-Line colors.
- Project layout uses a steady project half and a task-status half, with Shared overflow.
- The wall map supports multi-selection, color picking, half swapping, Locate, and rotation.

The integration runs on Windows. Installed WSL hooks forward to Windows Python so every process uses the same database locks. The Python tests and demo map run on Windows or Linux without lights or credentials. Runtime code uses the Python standard library.

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

GitHub Actions runs the Python suite on Linux and Windows with Python 3.12 and 3.14, workflow checks on both platforms, and browser checks on Linux.

After `npm ci`, run `npm run check:workflow` to validate OpenSpec work and
`npm run test:workflow` to exercise the validation commands. OpenSpec 1.12.0 is
pinned locally; use `npm run openspec -- <arguments>` instead of a global CLI.
Reusable skills come from the [shared catalog](https://github.com/jimmie-potts/agent-skills); see [setup](docs/development.md#shared-skills). This repository keeps no shared skill copies.
The [wall Line identification specification](openspec/specs/wall-line-identification/spec.md)
owns numbering, selection, and the Locate boundary. Other behavior remains
documented in [the bridge guide](bridge/README.md) until migrated through review.

## Installation

For an existing installation, run `bridge/install-modes.ps1` in Windows PowerShell. It backs up the program and private state, then restarts only this installation's worker, map server, and tray. A source checkout does not change the running installation.

For fresh setup, follow [the integration guide](bridge/README.md). This version retains the original machine's private controller IP as the setup default and expects Codex's bundled Windows Python runtime. It is a personal integration, not a general-purpose installer. See [development and deployment](docs/development.md) for the WSL workflow and limitations.

## Codex

Add this repository folder as a WSL project in Codex Desktop. The root [AGENTS.md](AGENTS.md) describes validation, state preservation, and runtime boundaries. [Codex setup notes](.codex/README.md) list test and demo commands for optional toolbar actions.

## Repository contents

| Location | Purpose |
| --- | --- |
| `bridge/` | Deployable Python bridge, local map, and Windows scripts |
| `tests/` | Isolated regression tests and browser checks |
| `tests/fixtures/` | Geometry fixture with substituted panel IDs |
| `scripts/` | Test runner and device-free demo |
| `.github/` | CI and pull request template |

Credentials, hook configuration, live databases, task metadata, scene preferences, screenshots, and installation backups are excluded from Git. No live state is required to run the tests.
