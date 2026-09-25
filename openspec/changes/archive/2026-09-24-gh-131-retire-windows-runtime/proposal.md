## Why

The Linux runtime has owned the lights since [#54](https://github.com/jimmie-potts/codex-nanoleaf/issues/54) and [#55](https://github.com/jimmie-potts/codex-nanoleaf/issues/55), and the owner decided to run no Windows-native components. The source still carries a Windows runtime that nothing runs or tests: a PowerShell installer and tray, WSL-to-Windows forwarding in the bridge, a Windows Python helper for MCP, and specifications and guides that present a Windows installation as supported. [Issue #131](https://github.com/jimmie-potts/codex-nanoleaf/issues/131) retires it from source so the Linux runtime is the only documented, specified and tested installation.

## What Changes

- **BREAKING** for legacy Windows installations only: the `install-modes.ps1` upgrade path, the tray, `bridge.py tray`, WSL-to-Windows forwarding of installed commands, and the `commandWindows` hook field are removed. The installed Linux runtime is unaffected; source delivery does not touch it.
- The bridge modules lose their `os.name == 'nt'` branches: forwarding in `main`, the tray command, the PowerShell remover in uninstall, `windows_path`, the `LOCALAPPDATA` data directory, and the Windows Codex-home defaults. The `/mnt/c` state-directory guards stay.
- The MCP host's direct transport gets the platform-neutral identifier `loopback-http`; `windows-http` remains an accepted alias so an installed `mcp-config.json` keeps validating. The `wsl-helper` transport, `mcp/windows-controller-http.py`, its probe, fixture and tests, and the `windows.json` and `wsl.json` examples are removed.
- Windows-only files are deleted: the PowerShell scripts, tray icon and its source, `backup_install.py`, `scripts/build-tray-icon.py`, and the PowerShell tests. The disabled GitHub Actions workflow loses its Windows matrix entries.
- ADR 0012 supersedes the Windows ownership and forwarding clauses of ADRs 0005 to 0007 and records the one remaining Windows touchpoint: read-only access to Codex Desktop's mounted JSON.
- Documentation describes Linux as the only supported installation. `docs/hardware-validation.md` stays as the retired Windows acceptance record with a note.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `protected-controller-api`: the "Supported modes preserve existing ownership" requirement drops the legacy Windows forwarding boundary and its WSL dispatch scenario; controller commands use the installation's Linux state and worker.
- `local-mcp-bindings`: hosting no longer promises Windows and WSL; the "Bounded Windows and WSL transport" requirement becomes a Linux loopback transport requirement with a platform-neutral identifier and accepted alias; source qualification covers the Linux template only.
- `integration-settings-api`: the "Portable bounded delivery" requirement drops retained Windows ownership and forwarding.

## Impact

`bridge/bridge.py`, `project_map.py`, `shared_input.py`, `wall_server.py`, `devices.py`, `install_linux.py`, `controller_state.py` (docstring); `mcp/src/config.ts`, `mcp/src/transport.ts`, MCP tests and examples; Python tests that reference Windows behavior; the disabled Actions workflow; the three specifications; ADR 0012; README, AGENTS.md, the bridge guide, the development, controller API, local MCP, integration API, shared input, SDLC and Linux installation guides, the OpenSpec context, and the PR and issue templates. No schema, state, device or wall page change. Shared-file coordination with [#118](https://github.com/jimmie-potts/codex-nanoleaf/issues/118) on `bridge.py` and `install_linux.py`.
