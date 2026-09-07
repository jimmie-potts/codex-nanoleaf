# ADR 0003: Adopt shared monitoring with the Windows controller

Status: Accepted direction; implementation pending. Scope: issue #27.

Adopt the hub's canonical shared architecture through
[the integration guide](../hub-integration.md). The hub owns provider contracts,
shared state, common APIs/MCP and the future overview. Nanoleaf retains its Python
Windows worker, effects, allocations, read policy, scenes and advanced editor.

Add a protected controller API and opt-in versioned session consumer before
an explicitly verified shared-input cutover. Preserve the legacy ingestion and
rollback path until then. Do not rewrite the worker, combine Windows/WSL database
access, or expose the browser's editing token as machine authentication.

The current user request supersedes permanent independent status collectors
in the earlier Pixoo plan. This decision changes planned ownership/dependencies;
it changes no current bridge, installed state, UI candidate or physical behavior.
No product specification delta applies to this documentation/backlog update.
