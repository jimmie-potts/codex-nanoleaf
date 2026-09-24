## Context

See proposal.md. The installed Linux runtime under `~/.local/share/codex-nanoleaf` is a copied snapshot with its own virtual environment, Node binary and `mcp-config.json` whose transport reads `windows-http`. The retired Windows installation still exists on the PC but runs nothing ([#132](https://github.com/jimmie-potts/codex-nanoleaf/issues/132) decommissions it). Depot CI is Linux-only. Every Windows branch in the bridge is guarded by `os.name == 'nt'` or by the installed path shape `Local\CodexNanoleaf`, so on Linux none of it executes today.

## Goals / Non-Goals

**Goals:** delete the Windows runtime and every claim that it is supported; keep the Linux runtime's behavior, CLI surface, state layout and installed configuration valid; keep the mounted-drive guards.

**Non-Goals:** no refactor of `bridge.py` beyond removing branches ([#118](https://github.com/jimmie-potts/codex-nanoleaf/issues/118) owns that), no change to hooks semantics, schema, wall page, device behavior, or the installed runtime; no launcher (ADR 0011).

## Decisions

- **Delete, do not abstract.** Each `os.name` branch is replaced by its Linux arm. Alternative: a platform module. Rejected because there is exactly one platform and the abstraction would be the code being removed.
- **Transport identifier.** The MCP config type becomes `transport: 'loopback-http'`; `loadConfig` normalizes `windows-http` to it and rejects `wsl-helper` and any helper key. The Linux installer writes `loopback-http`. Alternative: keep `windows-http` as the only name. Rejected because the name misdescribes the Linux route and the alias costs one line.
- **Hook registration returns one command.** `hook_command` returns a string and `merge_hooks` loses `windows_command`; `hooks register` output is unchanged for Linux.
- **Codex home defaults.** `unread_reader`, `Metadata` and `select_source` use `CODEX_HOME` or `~/.codex`; explicit `--desktop-state-path` and `--metadata-path` options keep pointing at mounted Windows JSON, which stays read-only.
- **ADR 0012** supersedes the Windows clauses of ADRs 0005, 0006 and 0007 and states the remaining Windows touchpoints: Codex Desktop's mounted JSON (read-only) and the Windows browser as a client.
- **Documentation.** `docs/hardware-validation.md` and the archived OpenSpec changes stay as history with a note; every current-facing guide describes Linux only. The scope-defaults sentence in `docs/sdlc.md` and the OpenSpec context drop legacy Windows.

## Risks / Trade-offs

- An operator who never upgrades the installed runtime sees no change; one who upgrades keeps a valid `mcp-config.json` because of the alias. Both are covered by tests.
- `hooks register` rollback to legacy input still works on Linux; it never needed `commandWindows` there.
- #118 touches the same modules. If it lands first, this change rebases onto the new module layout; if this lands first, #118's AC4 and AC6 lose their Windows packaging clauses.
- Recovery: the change is a revert. No state migrates, so nothing needs rolling forward.
