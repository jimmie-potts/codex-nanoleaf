## Context

See proposal.md for motivation and #54 for acceptance. The Python bridge already launches Linux workers and uses SQLite locks. The Node host already supports direct loopback HTTP. The remaining Windows dependency is installation, command forwarding, and platform-specific operating instructions.

## Goals / Non-Goals

Use one Linux installation with private state and the existing cooperating processes. Preserve the single light writer and existing API behavior. This design adds no state migration, combined service, hook endpoint, shared monitoring, or rollback system.

## Decisions

- Add `bridge/install_linux.py` as the fresh-install entrypoint. Keep the legacy Windows setup and installer available. Reuse the bridge's device validation, geometry pairing, hook merge, JSON writer, controller commands, and worker rather than refactoring the Windows installer.
- Store config, SQLite, credentials, and the Python virtual environment beneath the Linux state directory. Copy required runtime files under `runtime/bridge`, `runtime/mcp`, and `runtime/vendor` so the existing pinned package paths remain valid. Copy the selected native Node 24 executable into the installation for stable service startup. A small `nanoleaf` launcher invokes the private Python with the explicit state directory. Reject existing config and Windows-mounted state paths; a failed preparation can be retried in an empty project directory.
- Accept `--ip` and a hidden token prompt or private `--token-file`; accept explicit Desktop state, project metadata, and title-index paths. Use existing conservative readers. Never place a token in a process argument or browser response.
- Generated Linux hooks use the private interpreter and explicit state directory. Correct the hook CLI to honor that directory. Merge only this integration's marker entries; retain unrelated settings and handlers.
- Generate user service units for the foreground map, controller, and MCP processes, with owner-only umask and restart on failure. The installer does not start services or a worker. Operators enable/start the units in ordinary WSL after Windows retirement. Worker launches remain on demand, using the existing SQLite exclusive lock.
- Persist distinct loopback ports, defaulting to 8765/41231/41230. Add `serve --port` and `map --no-open`; Linux map commands print the URL without launching a browser. Preserve ephemeral defaults for existing source fixtures and legacy Windows installations without Linux port configuration. Port conflicts fail visibly rather than selecting a different configured port.
- Reuse the existing `windows-http` MCP transport identifier for Linux direct HTTP. A Linux example and generated config explain its compatibility name; no protocol or transport rewrite is needed. Generate separate controller and MCP credentials with fixed local target IDs; save the client token privately.

## Risks / Trade-offs

- Installed Codex hook permissions and WSL service-manager access require actual host evidence in #55. Source fixtures prove only their own Linux context.
- Metadata may be unavailable or change schema. Preserve existing conservative behavior and document the configured inputs.
- Windows and Linux workers cannot coordinate through a mounted SQLite lock. The operator retires this Windows installation before enabling Linux light control.
- User services follow WSL lifetime. No Windows startup automation or always-on guarantee is added.

## Installation handoff

Deliver reviewed source and documentation first. The separately authorized #55 stage retires the old Windows runtime, performs fresh Linux setup, starts user services, verifies one actual WSL task and browser/MCP access, and records a bounded visible-light sequence. Old project data can remain unused. No import, backup, rollback, or soak requirement applies.
