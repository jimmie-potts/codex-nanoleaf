# Development and deployment

The repository is the canonical source. The installed program in `%LOCALAPPDATA%\CodexNanoleaf` is a separate deployment with private credentials, its own SQLite state, and the remembered Nanoleaf scene. The original scratch workspace is historical and should not be used for future changes.

Follow [the SDLC guide](sdlc.md) for issue scope, planning, TDD, independent review,
and merge criteria. It also defines when installation is part of a task.

## Validate a change

Run `python3 scripts/check.py` from the root. The initial import has 100 tests. They exercise status transitions, read handling, comets, scenes, modes, project placement, split rendering, metadata recovery, and local HTTP validation. A successful run contacts neither a controller nor the real Codex state.

Run `npm run test:browser` after map or API changes. It starts the synthetic demo on an available loopback port and shuts it down afterward. Screenshots are written to ignored `test-results/`. To inspect the map manually, run `python3 scripts/demo.py` and open its printed URL.

Use Windows PowerShell for the tray and installer. `bridge/tray.ps1 -Check` verifies Windows Forms support and icon loading without starting a tray or worker. Run `tests/test_tray_icon.ps1` to check all six icon sizes with Windows, transparency, the blue/green palette, tray sizing, and missing or corrupt asset fallback. Hosted CI runs both checks; menu interaction still needs a Windows smoke check.

## Workflow tooling

Run `npm ci` to install the locked development dependencies. On WSL, if the user
npm cache is read-only, add `--cache /tmp/codex-nanoleaf-npm-cache`. The Python
regression suite still requires only the standard library.

`npm run openspec -- <arguments>` uses the pinned OpenSpec 1.12.0 CLI. The wrapper
disables telemetry and completion/animation prompts through child-process
environment variables. Each invocation uses a temporary CLI configuration
directory, which is removed afterward. This prevents OpenSpec's initialization
migration from changing user settings, even when `--profile core` is supplied.
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
archive fixtures and regeneration without user-configuration changes. CI runs
both commands in the always-running Workflow checks job, alongside the existing
product checks.

To regenerate the core Codex skills after an explicitly scoped OpenSpec upgrade,
use the local wrapper with `init --tools codex --profile core --no-animation`.
The explicit profile applies to that run. Do not change the global profile or
run a bare update that could select unrelated integrations. Review regenerated
instructions against the repository's composition rules. OpenSpec owns the
`openspec-*` skill directories; `nanoleaf-*` skills and project configuration own
the repository adaptations.

Use the installed skill-creator validator for authored skill structure, inspect
references, and test behavior with independent agents in isolated fixtures.
Record their actual actions and limitations in the PR. Do not treat a skill
description or a schema pass as proof of correct automatic selection.

## Upgrade the installed integration

Use `bridge/install-modes.ps1` from Windows PowerShell for an authorized upgrade. From WSL, a Windows process can access the source using its WSL UNC path. You can also copy the deployable `bridge` folder to a temporary Windows directory and run the installer there. Treat that copy as disposable staging and retain the WSL repository as the source.

The installer copies the bridge database using Windows SQLite and backs up the configuration, geometry, scene state, and existing program files. It preserves trusted hooks and task records. It then restarts the exact installed worker, map server, and tray. The tray's refresh resumes the saved mode. Reopen the map from the tray after an upgrade because its local port may change.

Do not use `bridge.py setup` for an upgrade. Fresh setup requests a credential, installs hooks, and clears task records. The `setup --refresh` command only redraws existing task state.

For physical checks, hold the installed Windows worker lock before sending isolated test effects. Hook-triggered workers can restart during testing, so verify lock ownership. Keep test tasks and scene choices in temporary state, then restore the latest real mode, layout, tasks, and scene preference before releasing the lock. Record controller readback separately from human confirmation of physical orientation.

## Current portability limits

The runtime is a personal Windows/WSL integration. Fresh setup defaults to the original private LAN address, and the tray locates the existing Codex Windows runtime under the user profile. The Codex metadata reader uses current desktop JSON fields that may change in future releases. These behaviors are preserved from the working installation; this repository setup does not change device discovery or hook semantics.

The geometry fixture retains the tested arrangement with arbitrary panel IDs. It contains no controller credentials or task metadata. Actual panel IDs and saved project reservations remain in the installation.

## Source import evidence

The starting implementation passed 100 tests in WSL and Windows. Prior physical readback covered split zones, overflow, both animation coverage choices, deferred comet edits, Quiet Locate, and scene restoration. Those historical results are context for the import. CI and new local runs provide evidence for later commits.
