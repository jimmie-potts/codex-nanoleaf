# 0006. Local MCP hosting for Windows and WSL

Status: Accepted for source implementation in [issue #33](https://github.com/jimmie-potts/codex-nanoleaf/issues/33).

## Context

Local Codex needs status and mode tools over the protected controller. The user selected support for Windows and WSL. The existing bridge keeps SQLite and all light writes on Windows, while the shared MCP module runs on Node 24 and supplies authentication, protocol and admission limits.

## Decision

Run an explicitly started Node 24 MCP host alongside each local client. Windows uses direct numeric-loopback HTTP. WSL invokes a configured Windows Python helper that exchanges bounded JSON over stdin/stdout and calls only the protected controller's snapshot/command routes. Keep the helper with the MCP source package; do not add it to bridge startup or install it as part of source delivery.

Bind status and Work/Quiet/Free service extensions to one configured target. Give each MCP principal a distinct upstream controller credential selected from private configuration. Do not forward incoming bearer tokens. Keep durable replay, mode admission, SQLite and physical serialization in the existing controller/worker. Failure after possible dispatch preserves uncertainty without retry.

## Consequences

Both client environments retain their workflows without a Windows LAN listener, firewall change or Linux database access. WSL needs an explicitly selected Windows runtime and durable helper path. The additional process has finite time/output limits and source fixtures. Starting/stopping MCP is independent of controller work. Credential provisioning, installation, actual client permission flow and physical acceptance remain #34.
