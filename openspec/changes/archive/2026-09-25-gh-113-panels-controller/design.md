## Context

The protected controller's state lives in the installation's `status.sqlite`:

- `controller_meta` holds a single row (`id=1`): identity, epoch, revision, generation, cursor, scene key and scenes, last send and last outcome, and the listener's `stopped` and `clockEpoch`.
- `controller_requests` and `controller_events` are keyed by one sequence space for the whole installation.
- Overrides and the hold are the meta keys `controller_power`, `controller_brightness` and `controller_hold_revision`.

Only the `wall` worker instance reads and executes this state ([ADR 0010](../../../docs/decisions/0010-per-device-worker-and-nl22.md)). Worker instances are already per device, and mode state already uses the ADR 0009 `key@device` meta names.

## Goals / Non-Goals

**Goals:**

- A ledger per configured device, owned by that device's worker, so each device keeps a single writer.
- The existing Lines ledger, its wire behavior and its fixtures stay unchanged.
- The optional MCP host can bind the Panels as a second fixed target.

**Non-Goals:**

- Per-device credentials.
- Extension configuration or animation commands for the Panels.
- Moving feed polling or the integration settings queue off `wall`.
- Hub changes, installation and physical checks.

## Decisions

1. **One table set with a `device` column.**
   - `controller_meta` gains `device TEXT NOT NULL DEFAULT 'wall'` and a unique index. The existing row keeps `id=1`.
   - `controller_requests` and `controller_events` are rebuilt with `device` as the last column and a `(device, sequence)` primary key. Their rows move over unchanged.
   - The migration is guarded and idempotent, and it runs inside `connect_state`'s initialization transaction, beside `devices.migrate`.
   - Keeping separate tables per device was rejected: it duplicates every query and still needs a key.
2. **Internal and external device identity.** The `wall` ledger is the original identity, whatever `deviceId` the operator configured for it (tests use `device`). Every other ledger is keyed by a registered device ID, and its external `deviceId` equals that ID. Routes resolve a requested `deviceId` by matching ledger identities.
3. **Configure adds a ledger; it never redirects one.** When the `wall` ledger has the same `controllerId` and `sourceId`, a new `deviceId` that names a registered device other than `wall` adds that device's ledger with its own epoch and scene key. Configuring an existing identity again changes nothing. Any other difference is rejected as a redirect, as before.
4. **Listener-wide flags live in every ledger.** `controller-serve` sets a new `clockEpoch` and `stopped=false` on every ledger. `controller-disable` sets `stopped=true` on every ledger and cancels every device's queued work. Issuing or revoking a token cancels that principal's queued work on every device and holds each affected device. Every per-ledger check then works unchanged.
5. **Credential devices are every configured ledger.** The shared contract authorizes a target by membership in `credential.devices`, so the controller fills that list with every ledger's external `deviceId`. An unknown target stays `forbidden` at authorization and `unknown-device` at identity match, as before.
6. **Per-device meta keys.** Overrides and hold use `devices.meta_key`, so `wall` keeps its unsuffixed keys. A controller `mode.set` and every local mode change (CLI, map) notify the target device's ledger, when it exists, through `controller_state.changed(device=...)`. A mode change supersedes only that device's queued controls. The integration extension retires animations only for a `wall` mode change.
7. **Worker ownership.**
   - Each instance recovers its own ledger's attempts at startup, stops on its own hold, and applies its own overrides.
   - Each instance journals its own mode writes and queued controls through `Execution(device=...)`, and records its own `discovered` scenes.
   - The `wall` instance keeps the poller, `integration_api.process`, requested animations and `integration_api.recover_attempts`.
   - An instance without a ledger behaves as before, because every ledger call is a no-op for an unconfigured device.
8. **Wake-up.** Admission still wakes every registered instance (`launch_worker`). An instance with nothing queued settles as before. Waking only the target is an optimization no requirement needs.
9. **Extension for other devices.** The snapshot keeps its exact key set, because the hub validates it closed.
   - It uses the device's identity, revision, mode and scenes, with no elements, no pending wall edit and no requests. The configuration operations are `supported: false`, and `nextRequestId` is the device ledger's ticket at sequence 0.
   - Commands fail with `unsupported-capability` before reservation.
   - Receipt and cancel return `request-expired`, because that device's epoch has no extension requests.
   - The animations route returns `unsupported-capability`.
10. **MCP.** An optional `panelsDeviceId` registers a second device in the shared module's registry with four service bindings (status, mode, scenes, scene activation), all under the `nanoleaf_panels_` prefix. The authenticated principal's `credential.devices` lists both device IDs, and `maxDevices` follows the configured count. Without the field, the host and tool list are unchanged.

## Risks / Trade-offs

- **Older source after the upgrade.** Older source reads the `wall` ledger (`id=1`) unchanged, but its positional insert into the rebuilt `controller_requests` fails. Admission then fails closed with `transport-failure`, and no device is written. Rolling source back therefore means accepting failed native admission until the upgrade is reapplied. Nothing in the installation downgrades automatically.
- **Two workers write the database concurrently.** Each device's controller work runs under the existing `BEGIN IMMEDIATE` passes and the five-second busy timeout that ADR 0010 already relies on. Controller rows are now partitioned by device, so one instance never finishes, holds or recovers another device's requests.
- **Crash between attempt and result.** This case is unchanged for each device: the owning instance's startup recovery marks the attempt uncertain and holds that device only.
- **Hub integration status for the Panels.** The hub's closed extension validator rejects `supported: false`, so the hub's integration status for the Panels fails with `incompatible-controller` until the hub accepts it. Hub v1 control and MCP don't use that validator.

## Migration Plan

`connect_state` migrates on the next hook, CLI, map, worker or listener start, and `controller-serve` migrates before its first read. A committed-style test builds the pre-change ledger (single-row meta, legacy request and event tables with rows), opens it, and checks three things: the identity, epoch, receipts, cursor, scenes and hold keys are preserved; a second run changes nothing; and replaying a retained request returns the same receipt.

## Open Questions

None. The owner settled ownership, credential scope and the extension scope at the checkpoint.
