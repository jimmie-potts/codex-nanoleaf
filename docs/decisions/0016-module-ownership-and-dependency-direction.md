# 0016. Shared operations have owning modules and one dependency direction

Status: Accepted on 2026-09-25 for source delivery of [#118](https://github.com/jimmie-potts/codex-nanoleaf/issues/118). It changes no behavior, schema, wire contract or CLI command.

## Context

`bridge.py` held the CLI, the light worker, rendering and the runtime primitives that every other module needed: opening the database, marking the display dirty, reading and changing modes, loading configuration and geometry, writing private JSON, device requests, launching workers and managing Codex hooks. Other modules received those primitives as a value. The CLI passed the bridge module itself, or `SimpleNamespace(**globals())`, to the shared-input, controller and enrollment commands. The wall map and controller apps kept it as `app.b`. The worker built another namespace for the shared-feed poller.

Configuration edits had a single implementation inside the browser adapter. `integration_api` translated each machine command into a browser route string such as `/api/settings` and imported `wall_server` to apply it. Several modules broke import cycles with function-level imports: `integration_api` imported `wall_server` and `controller_server`, `controller_server` imported `integration_api`, and `controller_state` imported `integration_api` to retire animations. [ADR 0008](0008-integration-settings-extension.md) had asked for shared transaction-level operations.

## Decision

Each shared operation has one owning module. Callers import it directly. No module imports `bridge.py`, and no function takes the bridge module or a namespace of its globals.

| Module | Owns |
| --- | --- |
| `jsonfile` | Private JSON files replaced in one rename |
| `transport` | `light_request`, the device's local HTTP API. It sends what the caller asks and renders nothing |
| `store` | The shared meta records: `mark_dirty` (display wake-up) and each device's `control_state` |
| `codex_hooks` | This integration's handlers in a Codex `hooks.json`, the span-preserving JSON parser, and `bridge.py hooks` |
| `configuration` | The state directory, the device registry, `load_config` and Lines zone pairing |
| `launcher` | Detached `bridge.py` processes: `launch_worker` still spawns `bridge.py worker` once per registered device |
| `edits` | Configuration edits shared by the wall map and the integration extension |
| `database` | `connect_state`: opens the state and initializes every owner's tables in one transaction |
| `modes` | The explicit mode command (`change_mode`, `set_mode`) and the read-only `get_status` |
| `shared_source` | Choosing and following the task source: configuration, switching, polling and acknowledgments. `shared_input` keeps the feed contract and its projection into local state |
| `bridge` | The CLI entry point, the worker loop, rendering, scene restoration and hook event handling |

`controller_state` also owns the admission transaction, its deadline check and the HTTP status for each machine failure code, because the native and extension routes share them.

**Configuration edits.** `edits` provides one operation per edit: map settings and palette, element assignment, project color, task project, Locate and eviction. Each runs inside the caller's write transaction. It validates its input against current state, applies it, and records the change once: one revision on each affected controller ledger and one display wake-up. A map edit that would move an active comet still waits as a pending wall edit. The browser adapter decodes each route's payload and keeps Host, Origin and edit-token checks. The machine adapter keeps authentication, strict request validation, opaque IDs and the request journal. It resolves opaque IDs into an edit, and applies that edit together with the receipt in the worker's transaction. Neither adapter carries its own copy of an edit.

**Mode commands.** `modes.change_mode` retires queued animations whenever the Lines has a controller ledger. Every explicit mode command reaches it, whether it comes from the CLI, the map or a native `mode.set`, so `controller_state` no longer imports `integration_api`.

**Dependency direction.** Module-level imports form an acyclic graph, from leaves to entry points:

1. `devices`, `effects`, `panels`, `project_map`, `controller_contract`, `jsonfile`, `transport`, `store`
2. `configuration`, `controller_state`, `shared_input`
3. `launcher`, `codex_hooks`, `edits`, `integration_api`
4. `database`, then `modes`, then `shared_source`
5. Entry points: `bridge`, `wall_server`, `controller_server`, `enrollment`, `install_linux`

A module imports only from earlier levels or earlier in its own level. Only two kinds of function-level import remain:
- `bridge.main` loads the controller, enrollment and wall-map command families only when one runs, so hooks and status never import HTTP listeners or optional packages.
- `controller_server` loads `controller_contract`, the optional listener dependency in `requirements-controller.txt`.

Outside the local modules, `shared_input` loads the vendored `agent_state` schema validator only when it checks a shared snapshot, so legacy startup never needs it.

`tests/test_module_dependencies.py` enforces the graph and these exceptions.

**Seams.** Each operation takes the dependency it actually uses:
- `request` for device reads and writes: layout discovery, enrollment, `setup --check` and the worker's transport.
- `send` for the worker's rendered-effect sender.
- `launch` for waking workers.
- `now` and `sleep` for the clock.

Device reads, enrollment requests and rendered-effect sends stay separate parameters. `bridge.main`, `setup` and the command families pass `launch` and `request` through, so tests and the synthetic demo run the real CLI and map without mutating any module.

## Consequences

- Process and state ownership do not change: one worker per device, one database and the same transactions, locks and timeouts.
- The Linux installer already copies every `bridge/*.py` except itself, so the new modules are packaged automatically. `test_copied_runtime_holds_and_starts_every_shared_module` imports each module from an isolated copy and runs the documented commands from it.
- Tests and the demo inject fakes through these seams. Patching an owning boundary (`transport.light_request`, `database.connect_state`, `jsonfile.write_json`) remains acceptable for failure injection.
- Follow-up work builds on these owners. [#120](https://github.com/jimmie-potts/codex-nanoleaf/issues/120) moves backup and seeding knowledge to state owners. [#121](https://github.com/jimmie-potts/codex-nanoleaf/issues/121) decides the worker's device context. [#122](https://github.com/jimmie-potts/codex-nanoleaf/issues/122) investigates a pure shared-input projection.
