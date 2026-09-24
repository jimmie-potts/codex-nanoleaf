# 0012. Retire the Windows runtime from source

Status: Accepted for source implementation in [#131](https://github.com/jimmie-potts/codex-nanoleaf/issues/131).

## Context

The bridge began as a Windows program: Windows Python owned the SQLite state,
a PowerShell tray started at sign-in, and WSL entry points forwarded every
installed command to Windows because Linux and Windows SQLite locks on one
mounted file do not exclude each other. [ADR 0005](0005-protected-controller-api.md),
[ADR 0006](0006-local-mcp-hosting.md) and [ADR 0007](0007-linux-runtime-ownership.md)
each kept that path for legacy Windows installations while adding the
controller API, the MCP host and the fresh Linux installation.

Since [#55](https://github.com/jimmie-potts/codex-nanoleaf/issues/55) the Linux
installation owns the lights; the legacy hooks were removed in
[#89](https://github.com/jimmie-potts/codex-nanoleaf/issues/89); the owner
retired the Windows tray, worker and shortcuts from the PC and decided to run no
Windows-native components ([ADR 0011](0011-runtime-availability-follows-wsl.md)).
Hosted CI is Linux-only, so the Windows code was neither run nor tested.

## Decision

Remove the Windows runtime from source. The PowerShell installer, tray and their
tests, the WSL-to-Windows forwarding and `commandWindows` hook variant, the
`tray` command, the Windows Codex-home defaults, and the MCP `wsl-helper`
transport with its Windows Python helper are deleted rather than kept behind
platform checks. The MCP direct transport is named `loopback-http`;
`windows-http` remains an accepted alias so an installed configuration keeps
validating. The `/mnt/c` state-directory guards stay, because they protect the
Linux runtime from a mounted-drive database.

The Windows clauses of ADRs 0005, 0006 and 0007 are superseded: no installed
command forwards to another operating system, no MCP route uses a helper
process, and the Linux installation is the only supported one. The remaining
Windows touchpoints are read-only: Codex Desktop's mounted JSON for unread and
title metadata, and the Windows browser as a wall-map client.

## Consequences

- Legacy Windows installations can no longer be upgraded from source. The retired
  installation on the PC is decommissioned under
  [#132](https://github.com/jimmie-potts/codex-nanoleaf/issues/132).
- Running the Python suite on native Windows is no longer claimed.
- `docs/hardware-validation.md` and the archived OpenSpec changes stay as
  history. Current guides describe Linux only.
- Restoring the Windows runtime would mean a thin client of the controller API,
  not this code; Git history keeps it if ever needed.
