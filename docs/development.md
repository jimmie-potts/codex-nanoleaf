# Development and deployment

The repository is the canonical source. The installed program in `%LOCALAPPDATA%\CodexNanoleaf` is a separate deployment with private credentials, its own SQLite state, and the remembered Nanoleaf scene. The original scratch workspace is historical and should not be used for future changes.

## Validate a change

Run `python3 scripts/check.py` from the root. The initial import has 100 tests. They exercise status transitions, read handling, comets, scenes, modes, project placement, split rendering, metadata recovery, and local HTTP validation. A successful run contacts neither a controller nor the real Codex state.

Run `npm run test:browser` after map or API changes. It starts the synthetic demo on an available loopback port and shuts it down afterward. Screenshots are written to ignored `test-results/`. To inspect the map manually, run `python3 scripts/demo.py` and open its printed URL.

Use Windows PowerShell for the tray and installer. `bridge/tray.ps1 -Check` verifies Windows Forms support without starting a tray or worker. The hosted CI check covers this prerequisite; menu interaction still needs a Windows smoke check.

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
