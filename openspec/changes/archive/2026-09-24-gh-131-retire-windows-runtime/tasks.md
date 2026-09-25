## 1. Executable behavior

- [x] 1.1 Add or update tests first and observe them fail: MCP config accepts `loopback-http` and `windows-http` and rejects `wsl-helper` and helper keys; the Linux installer writes `loopback-http`; `hook_command` returns one command and `merge_hooks` takes none for Windows; the installed-command surface has no forwarding. Verify: the new assertions fail on the unchanged code.
- [x] 1.2 Remove the Windows branches from `bridge.py`, `project_map.py`, `shared_input.py`, `wall_server.py`, `devices.py` and `install_linux.py`, delete the PowerShell files, tray assets, `backup_install.py`, `scripts/build-tray-icon.py` and the PowerShell tests. Verify: `python3 scripts/check.py` passes and `git grep` finds no `.ps1`, `commandWindows`, `powershell.exe`, `python.exe` or `os.name == 'nt'` outside the mounted-drive guards.
- [x] 1.3 Rename the MCP transport with the alias, remove `wsl-helper`, the helper, its probe, fixture, tests and the Windows examples. Verify: `npm run test:mcp` passes with the updated config and transport tests.

## 2. Specifications, decisions and documentation

- [x] 2.1 Write ADR 0012 superseding the Windows clauses of ADRs 0005 to 0007. Verify: the file exists with the next number and links the three superseded decisions.
- [x] 2.2 Sweep README, AGENTS.md, the bridge guide and the development, controller API, local MCP, integration API, shared input, SDLC and Linux installation guides, the OpenSpec context, the disabled Actions workflow and the PR and issue templates. Verify: `git grep -i windows` on current-facing docs returns only the read-only Codex Desktop JSON, the Windows browser, the historical acceptance record and the ADR history.
- [x] 2.3 Synchronize the three delta specs into the main specs and archive this change on the branch. Verify: `npm run check:workflow` and `npm run test:workflow` exit zero.

## 3. Delivery

- [x] 3.1 Run `python3 scripts/check.py`, `npm run test:browser`, `npm run test:mcp`, `npm run check:workflow` and `npm run test:workflow`; publish the PR with base, head, merge-base, the grep inventory and the spec-to-test mapping. Verify: Depot CI succeeds at the head and independent Standards and Specification reviews clear it.
