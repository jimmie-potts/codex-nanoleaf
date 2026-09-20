# Integration settings API

[Issue #49](https://github.com/jimmie-potts/codex-nanoleaf/issues/49) adds the
Nanoleaf-owned `nanoleaf.integration/1.0` extension. Its
[specification](../openspec/specs/integration-settings-api/spec.md) owns behavior.
The released shared controller v1 schema/archive is unchanged. The optional
controller listener serves both APIs on the same authenticated loopback endpoint.

## Operations and permissions

| Operation | Values | Permission and route |
| --- | --- | --- |
| Inspect configuration, identities, pending edits and receipts | One configured Lines device | Machine `read` |
| Work / Quiet / Free | Existing modes | Machine `control`, unchanged `/controller/v1/commands` |
| `settings.set` | `style`: `classic` or `project`; `coverage`: `whole` or `status` | Machine `control` |
| `elements.assign` | Stable physical Line ID, nullable project ID, optional `signature` 0 or 1 | Machine `control` |
| `task.assign` | Opaque task ID, nullable project override | Machine `control` |
| `project.color` | Opaque project ID, `#RRGGBB` saved color | Machine `control` |
| Cancel a configuration edit | Its original request ticket | Owning machine principal with `control` |
| Locate, preview, power, brightness, scene selection, source switching, orientation, new devices or combined layouts | Unsupported by this extension | No operation |

The four extension edits preserve the selected Work/Quiet/Free mode. They are
available in all three modes, using the existing wall application operations.
Classic preserves Project reservations. Coverage and half selection retain their
existing display meaning. A saved configuration does not prove a device send or
visible light output. Free continues to obey its existing handoff policy.

The Hub's native backend uses a dedicated machine principal. The Hub browser
must never receive that credential, the wall editing token or the device token.
It delegates to its backend; frontend implementation belongs to Hub #6. Read-only
principals cannot write or cancel. Exact Host, Origin and Fetch-Metadata checks,
loopback binding, framing, body/time limits and admission concurrency remain those
of the [controller API](controller-api.md). No CORS allowance is added.

## Routes

All paths below begin with `/controller/integration/v1`. Every call requires
`Authorization: Bearer <native machine credential>`.

| Method and suffix | Result |
| --- | --- |
| `GET /snapshot?deviceId=<configured-id>` | Sanitized snapshot and current extension request ticket |
| `POST /commands` | Admission receipt |
| `GET /receipt?deviceId=<id>&epoch=<epoch>&sequence=<sequence>` | Original principal's retained receipt, without effects |
| `POST /cancel` | Cancel queued work, or return an already completed receipt |

Example command, with values taken from the latest snapshot:

```json
{
  "apiVersion": "nanoleaf.integration/1.0",
  "controllerId": "local-controller",
  "deviceId": "wall",
  "requestId": {"epoch": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "sequence": 0},
  "expectedRevision": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "command": {"kind": "settings.set", "style": "project", "coverage": "status"}
}
```

`elements.assign` carries an `elements` array of objects with `id` and at least
one of `projectId` or `signature`. `task.assign` carries `taskId` and `projectId`;
null removes the override. `project.color` carries `projectId` and `color`.
Unknown properties and malformed values fail validation. The
[TypeScript consumer](../contracts/integration-v1/consumer.ts) and
[shared fixtures](../contracts/integration-v1/fixtures.json) specify these shapes.
The consumer has no network or automatic retry behavior.

Cancellation has exactly `apiVersion`, `deviceId` and the original `requestId`.
It cannot undo a committed configuration or a physical effect. Authorization and
principal/target checks happen before retained request lookup, including after
credential rotation or revocation.

## Projection and revisions

Snapshots expose `identity`, `configurationRevision`, `revision`, `mode`,
`settings`, `source`, `projects`, `tasks`, `elements`, `wallPending`, `pending`,
`outcomes`, `nextRequestId`, `capabilities` and `limits`. Current values and desired
pending edits remain separate. `wallPending` is null or an allowlisted object
with settings, element changes and task overrides. `pending` contains only the
caller's queued extension request; `outcomes` contains its latest 32 receipts.
Use the receipt route for older retained requests.

Local project/task IDs are opaque, controller-epoch-scoped identifiers. Automatic
project names, conversation titles, roots, raw provider metadata and credentials
are excluded. When shared input is selected, qualified task `sharedIdentity` and
project `sharedProjectId` map back to #29's feed. Inspection never switches sources,
refreshes metadata, allocates Lines, clears notices, marks tasks read, advances
animations, launches a worker or requests a device. Reads use one SQLite snapshot.

The opaque `revision` covers configuration, task/project associations, source
selection and pending wall changes. It also incorporates the existing controller
revision. Metadata/feed changes that affect identities or associations invalidate
it even if the controller counter stays unchanged. Changes in another task's
activity do not themselves restart effects. Clients must not derive or edit IDs
or revisions. Extension tickets use a sequence separate from controller v1.

## Admission and recovery

At most one configuration edit is queued. An identical pending request returns
202 and joins it; an identical retained completed request returns 200. Reusing a
ticket with different content conflicts. Foreign, expired and out-of-order tickets
cannot execute. Invalid, unsupported, stale and capacity-rejected requests consume
no ticket. After rejection, refresh before an explicit new user decision.

The worker applies queued edits through the same operation as the wall under its
write transaction, with an atomic receipt. It waits for active comets, preserving
their source reservations. Existing pending wall work rejects admission; a later
wall/mode/association edit invalidates queued extension work. Cancellation,
revocation, credential rotation and controller disable retire queued work. Work
expires after 30 seconds, including across listener/worker restarts. An unavailable
or held worker can leave a request queued until cancellation or expiry; these
configuration requests never clear a mode transport retry hold.

| Outcome | Meaning | Prior effects |
| --- | --- | --- |
| `queued` | Waiting for the worker and safe configuration boundary | `none` |
| `applied` | Configuration committed | `configuration` |
| `failed` | Configuration not applied; inspect bounded failure code | `none` |
| `cancelled` | Queued edit retired | `none` |

Every receipt has `physicalOutcome: "unknown"`. The extension cannot attribute
subsequent rendering, partial transmission or optical results to a saved edit.
The existing mode API retains its separate transport evidence. A lost response
is uncertain to the client: look up the original receipt, do not reconnect with
a fresh write. If a receipt has expired, effects remain unknown; inspect current
state and require another explicit decision. A later cancellation returns an
already applied receipt without claiming reversal. Launch failure cannot erase
an application already committed by a running worker.

HTTP failures retain controller codes: 400 invalid, 401 unauthenticated, 403
forbidden, 409 conflict/order, 410 expired, 422 unsupported, 429 capacity, 503
launch/service failure. Reads return capacity instead of silently truncating an
editable identity map. Limits are 1,000 projects/tasks/reservations, 300 configured
Lines, one queued edit, 256 retained completed receipts and 65,536 request bytes.
The existing controller thread, socket, transaction-deadline and body limits apply.

## Runtime, versioning and rollback

[ADR 0008](decisions/0008-integration-settings-extension.md) records ownership.
Linux uses its private native SQLite and direct loopback listener. Legacy Windows
uses its Windows-owned SQLite and existing Windows/WSL forwarding. A development
checkout never opens installed state. Additional devices require qualified
capabilities and per-device ownership in #41/#44; no combined layout is implied.

A future incompatible contract uses a new extension version/path. Consumers
must reject unknown versions and unsupported operations, not fall back to wall
credentials or arbitrary native commands. Rolling source back retains the current
database: cancel queued edits, stop this installation's listener and worker through
the existing operator procedure, then restore prior program files. Older source
ignores extension tables. Do not run fresh setup or restore an old database over
new tasks. Cancelled/expired tickets cannot become new work on later upgrade.

Run `python3 scripts/check.py` with native Node 24 on PATH for cross-language
fixtures, plus `npm run test:browser`, `npm run check:workflow` and
`npm run test:workflow`. Hosted Python checks use Node 24 on Windows and Linux.
Windows installer fixtures verify module packaging; forwarding fixtures retain
native-OS routing. These are source checks, not installed-client or physical proof.
