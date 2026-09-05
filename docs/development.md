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
archive fixtures and regeneration without user-configuration changes. CI runs
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
./scripts/manage-skills.sh install --agent codex github-delivery tdd grill-with-docs grilling domain-modeling code-review openspec-propose openspec-explore openspec-apply-change openspec-update-change openspec-sync-specs openspec-archive-change
./scripts/manage-skills.sh status --agent codex
```

The manager links each selected skill to that checkout and preserves conflicts.
Keep that checkout available. Restart Codex when it needs to refresh skill
metadata. TDD and Grill with Docs retain their global explicit-only settings;
Nanoleaf's agent instructions deliberately compose them within authorized work.
That routing is separate from host discovery. A missing skill must be installed
or reported, without creating a local copy as a fallback.

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

Use `bridge/install-modes.ps1` from Windows PowerShell for an authorized upgrade. From WSL, a Windows process can access the source using its WSL UNC path. You can also copy the deployable `bridge` folder to a temporary Windows directory and run the installer there. Treat that copy as disposable staging and retain the WSL repository as the source. Pass `-SkipShortcuts` when upgrading an existing installation without write access to the Start Menu. This preserves both existing shortcuts, including their previous icons; the tray artwork and installed program files still update.

The installer copies the bridge database using Windows SQLite and backs up the configuration, geometry, scene state, and existing program files. It preserves trusted hooks and task records. It then restarts the exact installed worker, map server, and tray. The tray's refresh resumes the saved mode. Reopen the map from the tray after an upgrade because its local port may change.

Do not use `bridge.py setup` for an upgrade. Fresh setup requests a credential, installs hooks, and clears task records. The `setup --refresh` command only redraws existing task state.

For physical checks, hold the installed Windows worker lock before sending isolated test effects. Hook-triggered workers can restart during testing, so verify lock ownership. Keep test tasks and scene choices in temporary state, then restore the latest real mode, layout, tasks, and scene preference before releasing the lock. Record controller readback separately from human confirmation of physical orientation.

## Current portability limits

The runtime is a personal Windows/WSL integration. Fresh setup defaults to the original private LAN address, and the tray locates the existing Codex Windows runtime under the user profile. The Codex metadata reader uses current desktop JSON fields that may change in future releases. These behaviors are preserved from the working installation; this repository setup does not change device discovery or hook semantics.

The geometry fixture retains the tested arrangement with arbitrary panel IDs. It contains no controller credentials or task metadata. Actual panel IDs and saved project reservations remain in the installation.

## Source import evidence

The starting implementation passed 100 tests in WSL and Windows. Prior physical readback covered split zones, overflow, both animation coverage choices, deferred comet edits, Quiet Locate, and scene restoration. Those historical results are context for the import. CI and new local runs provide evidence for later commits.
