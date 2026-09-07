## Context

The controller merged in #28 owns pure snapshots, mode admission and all Windows SQLite work. Its declared capabilities support Work, Quiet and Free; brightness is policy within those modes, not an exposed setter. Hub #7 provides authenticated HTTP MCP, session/resource limits and fixed service extensions. Generic bindings would advertise unsupported power and brightness tools, so this consumer uses service extensions.

The user explicitly selected both Windows Codex and the existing WSL workflow. The coordinator inspected Codex CLI 0.153.4 and its `mcp add --url --bearer-token-env-var` help. This establishes template syntax only. Real client connection and permission behavior remain acceptance work.

## Goals and non-goals

Expose the current controller through the shared MCP package with one device writer and one request ledger. Keep native client credentials, upstream credentials and browser tokens separate. Preserve exact receipt identity and uncertainty across client or helper failure.

No new light capabilities, installed service, database, automatic command retry, LAN listener, firewall changes, provider migration or personal configuration writes are included.

## Decisions

### Host and transport

An explicitly launched Node 24 process runs alongside Codex, bound only to `127.0.0.1` at an operator-selected fixed port. Only exact `/mcp` is routed to the shared handler before any body parser. Host is exactly `127.0.0.1:<port>` and supplied Origin is exactly its HTTP origin. Native requests without Origin still require authentication. SIGINT/SIGTERM close new admission and bounded client delivery; they do not stop controller work.

On Windows, the adapter uses `node:http` to the configured `127.0.0.1` controller port. On WSL, it spawns an explicitly configured Windows Python executable with a trusted Windows path to `mcp/windows-controller-http.py`. Use an argument array with `shell:false`. No auto-discovery, state file reads or arbitrary URL/path tool fields are needed. The helper remains part of the separate source MCP package; #33 need not modify the bridge installer. Later acceptance selects a durable Windows source path and provisions the controller's fixed port.

The helper reads one strict bounded JSON document from stdin and emits one bounded JSON response. Its operation enum is `snapshot` or `command`; it constructs the two fixed controller routes itself. The input carries the configured port/device, selected upstream credential and validated request. These values come only from the host configuration and validated tool input. The helper imports no bridge/SQLite code, never launches a worker, uses `http.client.HTTPConnection` to numeric loopback, follows no redirects, and ignores proxy variables. Credentials never appear in argv, logs, returned errors or MCP output.

### Configuration and credentials

Use explicit private JSON paths outside the checkout. Startup configuration fixes transport, MCP/controller ports, controller/device IDs and WSL runtime/helper paths. Validate exact keys, bounded ASCII IDs and port ranges before listening. A separate bounded credential document holds up to 32 unique principals, one SHA-256 MCP bearer digest per principal, allowed read/control scopes and one dedicated upstream controller bearer per principal. Reject duplicate digests, principal IDs and upstream credential values. Tokens are provisioned outside source delivery; require sufficiently long opaque values and cap their length at 512 characters.

Read at most 65,536 bytes of the credential document on every authentication check and again immediately before adapter dispatch. Reject missing, oversized, malformed, revoked or invalid configuration without using cached credentials. Use constant-time digest comparison. Rotation keeps the configured principal ID; removal rejects new calls. Reissuing its controller credential follows #28's existing revocation/cancellation rules. Operators replace the credential file atomically and restrict its OS permissions. An incomplete replacement fails closed and cannot affect ordinary bridge use. No incoming MCP bearer is forwarded upstream. Authentication and dispatch both derive scopes and the selected upstream credential from current configuration; a principal removed or downgraded between them cannot dispatch a new write.

### Tools and results

Register one immutable controller/device and only two extensions through `bindServiceTools`. `nanoleaf_status` accepts an empty strict object. `nanoleaf_mode_set` requires `requestId`, `expectedConfigurationRevision`, `expectedGeneration` and `mode` in Work/Quiet/Free. The adapter adds the fixed target, API version and `mode.set` command. Embed shared schema definitions in strict extension schemas and validate snapshot/receipt data with the released shared validator. Verify returned target and command receipt request identity, not just schema shape.

Return schema-valid domain results, using `isError:true` for failures. A valid receipt is preserved byte-for-value as JSON, including queued/cancelled/sent/uncertain outcome, revisions and operation arrays. An explicit valid controller pre-admission failure retains its failure code and `priorEffects:none`. A write whose transport may have dispatched but yields timeout, malformed response, wrong identity, redirect or child exit returns `uncertain-result`, `priorEffects:possible` and the original request ID. Do not invent receipt revisions. Failure before any dispatch may use `transport-failure` and `priorEffects:none`; if dispatch cannot be disproved, preserve uncertainty. Reads may return a bounded unavailable result without fabricated snapshot fields. Never automatically retry. Recovery means a new status read or an explicit replay of the exact original request through #28.

### Bounds

Retain shared limits: 65,536 request bytes, 1 MiB full MCP response, 32 outstanding operations, 16 sessions, one configured device, one-second authentication, ten-second delivery budget and five-minute idle sessions. Set listener header/body timeouts and header count/bytes explicitly before routing.

Bound each controller exchange to six seconds total, 65,536 request bytes and 512 KiB response bytes. This exceeds the controller's five-second connection budget but fits the shared ten-second budget. Cap helper stdout at the response envelope allowance and stderr at 4 KiB. Kill an overrun helper and settle its promise; retain possible effects after dispatch. Keep at most the shared 32 active adapter exchanges. HTTP and child operations must settle even when clients disconnect. Total deadlines supplement socket timeouts, which alone do not bound trickle responses. Validate JSON depth and exact keys before serialization and after parsing.

## Risks and recovery

WSL interop and explicitly selected executable/helper paths can be unavailable. Fail before state access and describe the fixed configuration problem without leaking paths or credentials in tool results. Source tests exercise actual Windows Python as well as fake child failures; they do not prove installed routing.

A controller may admit work before the host loses its response. Shutdown, reconnect and credential changes cannot undo that work. The existing controller handles durable replay, generations, held uncertainty and one writer. The MCP host stores no receipt ledger. A current snapshot exposes recovery identity; deliberate exact replay remains the caller's choice.

## Validation

Both qualified MCP versions, 2025-11-25 and 2025-06-18, must run real initialization/discovery/status/mode/authentication/cancellation tests against a fake controller. Test both direct and helper routes, current credential replacement, strict targets/schemas, duplicate/conflicting/stale identities, concurrent calls, delayed results, malformed responses and operation bounds. Assert exact receipt preservation and zero automatic retry. A missing runtime or invalid helper input must not import bridge/SQLite or launch a worker.

Run new Node tests on Windows and Linux Node 24, helper tests on Python 3.12/3.14 for Windows/Linux, the repository Python suite after helper addition, browser regressions for the integration boundary, and both workflow checks. Keep source evidence separate from #34. Pin the final Hub release only after the coordinator verifies the archive, receipt, installed manifest and bundled contract. No placeholder pin may ship.

## Migration plan

This source change requires no database migration or bridge installation. Later authorized acceptance provisions private files and starts the host explicitly. Stopping the host and removing its Codex entry restores the previous client configuration while existing controller work remains independently owned. Preserve the Windows bridge and its state.
