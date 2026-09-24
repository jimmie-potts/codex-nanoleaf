# 0011. Runtime availability follows WSL until hub hosting

Status: Accepted on 2026-09-24 for [#133](https://github.com/jimmie-potts/codex-nanoleaf/issues/133).

## Context

Under [ADR 0007](0007-linux-runtime-ownership.md) the Nanoleaf runtime moved to
Linux: private state under `~/.local/share/codex-nanoleaf`, one light-writing
worker per device, and the wall map, controller API and MCP host as three user
systemd units created by the Linux installer. On the owner's PC the hub's shared
monitor runs as a fourth user unit, installed separately under
[#30](https://github.com/jimmie-potts/codex-nanoleaf/issues/30); ADR 0007 itself
did not adopt shared monitoring. The legacy Windows tray, which started at
Windows sign-in and launched the worker, has been retired from the PC, and
[#131](https://github.com/jimmie-potts/codex-nanoleaf/issues/131) plans to
remove the Windows runtime from source.

Those user units are wanted by `default.target`, so they start with the user's
systemd instance, not with the distribution itself, and the user has lingering
disabled. Nothing on Windows starts the distribution or a user session after a
sign-in or reboot. Until a WSL session exists, the lights, the wall map, the
controller, the MCP host and the shared monitor are unavailable. Hooks are Linux
commands that run inside WSL, so no hook event is raised before that; tasks that
run natively on Windows have no Nanoleaf hooks at all. The
[`linux-runtime` specification](../../openspec/specs/linux-runtime/spec.md)
states that availability follows WSL lifetime without Windows startup
automation, and ADR 0007 records that "WSL lifetime governs availability."

The owner's direction is to run no Windows-native components for this project.
Three options were considered:

1. One Windows-side launcher, a Startup entry or scheduled task that runs
   `wsl.exe` at sign-in, documented as the single accepted exception. Rejected
   because it is exactly the kind of Windows artifact the owner is removing, and
   because it would also need WSL idle shutdown disabled to keep the services up.
2. Manual start with an availability indicator in the wall map and hub.
   Rejected because the indicator adds a feature whose only purpose is to
   report a gap the hosting move removes; the owner accepted manual start
   without it for the interim.
3. Hosting off WSL through the hub's plans:
   [agent-device-hub#42](https://github.com/jimmie-potts/agent-device-hub/issues/42)
   (Docker on the PC) or
   [agent-device-hub#44](https://github.com/jimmie-potts/agent-device-hub/issues/44)
   (dedicated server). Chosen: it removes the dependency on WSL lifetime rather
   than working around it, and it keeps this repository free of Windows
   automation. Docker Desktop on the PC would carry the same sign-in dependency
   unless it autostarts, so hub #42 must settle that before it satisfies
   this decision; hub #44 does not have the dependency.

## Decision

Option 3. This project adds no Windows-side launcher, scheduled task or Startup
entry, and no availability indicator of its own. Availability keeps following
WSL lifetime, as the specification already states, until the hub's hosting work
moves the runtime off WSL. Those hub issues own the hosting change; this
repository revisits availability when one of them becomes ready.

In the meantime the operator starts the runtime by opening a WSL session as the
installing user, for example a WSL terminal. Whether a Codex Desktop task that
runs in WSL, or a Claude Code session in the distribution, creates the user
session that starts these units has not been measured.

## Consequences

- After a reboot, the map, the controller, MCP and the shared feed are
  unavailable until a user session starts the units. Lights may come up earlier,
  because a hook running in a WSL process starts the worker when needed. When
  shared input is selected, the consumer resyncs to the current snapshot;
  intermediate events are not replayed.
- This decision adds no Windows artifact, so once
  [#131](https://github.com/jimmie-potts/codex-nanoleaf/issues/131) and
  [#132](https://github.com/jimmie-potts/codex-nanoleaf/issues/132) finish, the
  Windows retirement is complete rather than "all but one launcher".
- The `linux-runtime` specification and the installation guide keep their
  current wording; this decision records why and links the hosting owners.
- Two conditions are unmeasured: whether the units stop when the last user
  session closes while the distribution stays up, and whether WSL's idle
  shutdown stops the distribution once no session is open. If the services are
  found stopped while the PC is on, reopen
  [#133](https://github.com/jimmie-potts/codex-nanoleaf/issues/133) with the
  observation. `loginctl enable-linger` is a Linux-side mitigation for the first
  condition and would not violate this decision.
- Supersedes nothing. ADR 0007's statement that WSL lifetime governs
  availability stands, now as a deliberate choice rather than a bootstrap gap.
