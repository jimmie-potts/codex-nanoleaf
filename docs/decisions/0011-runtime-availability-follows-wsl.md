# 0011. Runtime availability follows WSL until hub hosting

Status: Accepted on 2026-09-24 for [#133](https://github.com/jimmie-potts/codex-nanoleaf/issues/133).

## Context

Under [ADR 0007](0007-linux-runtime-ownership.md) the Nanoleaf runtime moved to
Linux: private state under `~/.local/share/codex-nanoleaf`, one light-writing
worker per device, and the wall map, controller API, MCP host and shared monitor
as user systemd services. The legacy Windows tray, which started at Windows
sign-in and launched the worker, has been retired from the PC, and
[#131](https://github.com/jimmie-potts/codex-nanoleaf/issues/131) removes the
Windows runtime from source.

The Linux services start when the Ubuntu distribution boots, but nothing on
Windows starts the distribution after a sign-in or reboot. Until a WSL session
opens, hooks, the wall map, the controller and the hub feed are unavailable.
The [`linux-runtime` specification](../../openspec/specs/linux-runtime/spec.md)
states that availability follows WSL lifetime without Windows startup automation.

The owner's direction is to run no Windows-native components for this project.
Three options were considered:

1. One Windows-side launcher, a Startup entry or scheduled task that runs
   `wsl.exe` at sign-in, documented as the single accepted exception.
2. Manual start, with the wall map and hub showing the runtime as unavailable.
3. Hosting off WSL through the hub's plans:
   [agent-device-hub#42](https://github.com/jimmie-potts/agent-device-hub/issues/42)
   (Docker on the PC) or
   [agent-device-hub#44](https://github.com/jimmie-potts/agent-device-hub/issues/44)
   (dedicated server).

## Decision

Option 3. This project adds no Windows-side launcher, scheduled task or Startup
entry, and no availability indicator of its own. Availability keeps following
WSL lifetime, as the specification already states, until the hub's hosting work
moves the runtime off WSL. Those hub issues own the hosting change; this
repository revisits availability when one of them becomes ready.

In the meantime the operator starts the runtime by opening any WSL session.
Codex Desktop tasks that run in WSL, a WSL terminal or a Claude Code session in
the distribution all start it, and systemd then starts the four services.

## Consequences

- After a reboot, lights and the shared feed stay dark until the first WSL
  session opens. Hook events before that are lost; the shared monitor catches up
  from the hub feed once running.
- No Windows artifact exists for this project, so the Windows retirement in
  #131 and #132 is complete rather than "all but one launcher".
- The `linux-runtime` specification and the installation guide keep their
  current wording; this decision records why and links the hosting owners.
- Whether the distribution stays up after the last interactive session closes
  has not been measured. If the services are found stopped while the PC is on,
  record the observation on #133's successor and reconsider option 1 or an
  earlier hosting move.
- Supersedes nothing. ADR 0007's "no Windows startup launcher or always-on host"
  statement stands, now as a deliberate choice rather than a bootstrap gap.
