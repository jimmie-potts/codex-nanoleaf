# Shared task input

[Issue #29](https://github.com/jimmie-potts/codex-nanoleaf/issues/29) adds the shared
session consumer. The [shared consumer specification](../openspec/specs/shared-session-consumer/spec.md)
owns its behavior. Legacy input remains the default. Software delivery and
configuration do not select shared input or install agent hooks.

The shared owner interprets agent observations. Nanoleaf validates its snapshots
and maps them to the existing Lines allocation and effects. The same Python
worker remains the sole light writer. Work, Quiet and Free are independent of
source selection. Linux state stays on Linux; retained Windows state stays on
Windows. Never share live runtime SQLite across operating systems.

## Prepare a source

Use the selected installation's Python runtime with the dependencies in
`requirements-controller.txt`. The consumer pins Agent State 1.0.0 from
[the immutable release](https://github.com/jimmie-potts/agent-device-hub/releases/tag/agent-state-v1.0.0),
archive SHA-256 `ae589d311e282c3356579c85507a3aa973ab7990e06e062143aeb08d8d2dcc99`.
Its unchanged Python validator, schemas and fixtures are extracted alongside the
archive. Legacy input does not import the optional validator dependency.

The initial host is Pixoo's `/api/monitor/v1` on numeric loopback. Provision the
Nanoleaf consumer **when initializing the shared host** with:

```json
{"id":"nanoleaf","clearOnNewTurn":true}
```

The released host preserves this consumer policy in durable state. Changing an
existing host's configuration from false to true does not migrate that state;
startup rejects mismatched policies. Do not reset or edit its database. Hub #8
owns installation and any supported policy migration. A new source setup must
use the chosen policy from initialization; an existing incompatible owner needs
that separately delivered migration before cutover.

Qualify the producer versions and paths, then provision a dedicated host read
credential. Keep its token in an owner-only regular file outside Git. Optional
explicit acknowledgment requires a separate control credential. Neither token
is the device credential or a wall-map browser token.

Create an owner-only private configuration file, substituting your declared
neutral identities and paths:

```json
{
  "version": 1,
  "ownerId": "monitor-owner-1",
  "consumerId": "nanoleaf",
  "endpoint": "http://127.0.0.1:8788/api/monitor/v1",
  "tokenFile": "/private/nanoleaf/monitor-read-token",
  "controlTokenFile": "/private/nanoleaf/monitor-control-token",
  "clearOnNewTurn": true,
  "qualifiedSources": [
    {"provider":"codex","client":"desktop","hostId":"host-1","sourceId":"desktop-1"}
  ],
  "bindings": []
}
```

Omit `controlTokenFile` when explicit acknowledgment is not needed. Every source
present in the selected feed must be declared qualified. The consumer verifies
feed authentication, version, owner, schema, revision and declared source
identities. The feed does not expose consumer policy or producer qualification;
those configuration declarations are operator assertions, not discovered proof.
Installed qualification belongs to Hub #8 and Nanoleaf #30.

## Select input

These are commands for a separately authorized installation. Use its wrapper
or Python entry point, never a development checkout pointed at live state.
Linux wrapper examples:

```sh
nanoleaf shared-configure --config /private/nanoleaf/shared-input.json
nanoleaf shared-preflight
nanoleaf shared-select shared
nanoleaf shared-status
```

Configuration persists privately in this installation's SQLite. Selecting shared
performs preflight again, then atomically changes source and presentation. The
owned legacy hook handler stops updating sessions; it neither alters unrelated
hooks nor sends provider payloads to the feed. Hub #8 owns actual producer/hook
provisioning. An active completion comet prevents source switching until its
reservation finishes. Switching resets completion comets and display caches on
every registered device and keeps each device's bound placements; the
`shared-select` output reports this as `"resetDevices": "all"`.

The Lines worker instance polls at most once per second with one request in flight;
other device instances render the projected tasks and a failed Lines pass does not
restart the feed as a resync.
Transport has a 2.5-second total deadline, a 16 MiB response ceiling, no proxies
and no redirects. Current-snapshot recovery avoids replaying intermediate events.
Wall-service startup resumes a previously selected shared worker. The existing
worker lock rejects duplicate worker processes; a held device command does not
stop shared-state polling. Linux runtime availability still follows WSL and its
services. Source delivery creates no personal service or listener.

Legacy Windows commands use the same `shared-*` operations through the installed
Python bridge; retained WSL entry points forward to Windows before opening state.
Source fixtures, hosted CI, and local Windows checks do not prove installed forwarding or light output.

## Task continuity and rollback

Sessions use the full provider/client/host/source/session identity. Several
sessions in one project remain separate. Shared project IDs and labels must be
explicitly chosen upstream. No local automatic title or path is uploaded.

For an existing task whose assignment should survive cutover, add an explicit
binding before selecting shared:

```json
{"identity":{"provider":"codex","client":"desktop","hostId":"host-1","sourceId":"desktop-1","sessionId":"task-1"},"legacySessionId":"task-1"}
```

Put this entry in `bindings`. Matching raw IDs alone are insufficient. Bound
assignments, local project preferences and matching status epochs transfer.
Unbound legacy tasks remain in the private rollback projection rather than
being confused with new shared sessions. Local manual task-project preferences
remain local. Shared project identities use their own namespace.

```sh
nanoleaf shared-select legacy
```

After shared input is selected, remove the marked legacy hook from each Codex
home with `nanoleaf hooks remove --codex-home <path>`. This edits only the
Nanoleaf-marked handlers and keeps a private backup; it does not change modes,
tasks or device state. The command refuses while legacy input is selected.
Before rolling back, restore the hooks in every relevant home, then select
legacy input:

```sh
nanoleaf hooks register --codex-home <path>
nanoleaf shared-select legacy
```

Legacy selection refuses when its configured `$CODEX_HOME` has no marked
Nanoleaf hooks and names `hooks register` in its diagnostic. Register hooks in
each Codex home used by the installation, including separate WSL CLI and
Windows Desktop homes.

Rollback restores retained legacy tasks and current bound presentation choices,
while preserving current modes, scenes, project colors and Line reservations.
It cancels old celebrations and holds restored colors steady until new local
hook evidence arrives. Events deliberately ignored during shared mode cannot
be reconstructed as legacy events. Do not restore an old whole database or run
fresh setup. There is no automatic fallback when the shared host disappears.

## Notices, freshness and health

A new evidenced turn clears earlier notices **for the Nanoleaf consumer** through
the owner's `clearOnNewTurn` policy. Unknown ordering does not prove a new turn;
ambiguous notices remain retained. Turn end does not imply successful work.
Read evidence is optional and separate: qualified read evidence can suppress the
local blue indicator without acknowledging the shared notice. Missing Claude or
Codex read evidence stays unknown. Legacy unread clearing remains unchanged.

Explicit acknowledgment targets a session key and exact notice ID. Obtain them
from the authenticated shared feed; `shared-status` exposes sanitized session
keys and health. For a configured control credential:

```sh
nanoleaf shared-acknowledge --session shared-IDENTITY_HASH --notice NOTICE_ID
# Only after an uncertain response, retry the same retained intent explicitly:
nanoleaf shared-acknowledge --session shared-IDENTITY_HASH --notice NOTICE_ID --retry
```

The command persists its server-issued request identity before sending. A lost
response leaves that intent pending; no new identity or automatic retry is used.
An expired request requires operator reconciliation with the shared owner.
Acknowledgment never marks a chat read or dismisses another consumer's notice.

### Subagents and retained notices

A session with an evidenced parent, such as a Codex subagent, is part of its
nearest top-level ancestor's task. It is not a task of its own. Its blocked or
question attention and the owner's count of its fresh activity raise the parent
task. Its turn-ended notices never make the parent unread: the owner records a
subagent's turn as unknown, so those notices cannot clear on a new turn. A task
is current only when a current member supplies its displayed status. A current
subagent alert therefore shows normally under an uncertain parent, and its
resolution takes effect steadily. An alert held only by uncertain subagents
shows steadily with uncertain evidence, even over a lower retained or current
status. Working follows the owner's count of fresh active subagents, so a silent
subagent never holds a current parent working. Under an uncertain parent, the
task keeps its last color until the members that supplied it, including that
subagent, return with current evidence. A completion that an active subagent
delayed shows without its completion comet
([#81](https://github.com/jimmie-potts/codex-nanoleaf/issues/81)). When the
topmost ancestor present in the snapshot has a missing parent, that group
appears only while it has blocked or question attention. Parentage that the
owner marks ambiguous leaves a session top-level, with its own notices. Legacy
hooks attributed subagent events to the parent session in the same way.

A top-level completion notice legitimately stays unread until one of these
happens:

- a new turn starts in the same session, which clears it under `clearOnNewTurn`;
- qualified read evidence reports the session read;
- someone explicitly acknowledges the exact notice for consumer `nanoleaf`.

Hub 0.2.2 reports Codex Desktop read evidence
([Hub #191](https://github.com/jimmie-potts/agent-device-hub/issues/191)), so
reading a finished task in Codex clears its indicator. Hub 0.2.3 forgets a
session after 24 hours without lifecycle evidence
([Hub #195](https://github.com/jimmie-potts/agent-device-hub/issues/195)), which
removes its task and notices here. A turn the owner could not order keeps its
earlier notice until a new eligible start, read evidence or an acknowledgment. Nanoleaf does not clear
notices by age, bulk-acknowledge them or read Codex state in shared mode.

To clear one retained notice, acknowledge it for consumer `nanoleaf`, either
through the Hub dashboard's monitor acknowledgment or with the
`shared-acknowledge` command above. The dashboard needs a Hub control
credential; the command needs this configuration's `controlTokenFile`. A
read-only credential allows neither. Continuing the conversation in Codex also
clears the notice.

On disconnect or uncertain session evidence, retain the last task colors steadily
and stop affected pulses/comets. Keep assignments and notices. One change still
applies while uncertain: a retained unread task becomes idle when the owner
reports it read or every notice acknowledged for `nanoleaf`
([#88](https://github.com/jimmie-potts/codex-nanoleaf/issues/88)). The change is
steady, and the freed Line goes to the next waiting task. Other retained colors
wait for current evidence. Healthy sessions
continue normally; Free remains free of task-light writes. Recovery preserves
existing phases and suppresses old outward waves and celebrations.

An uncertain Codex approval with no request ID remains red. The shared owner can
retire one such marker through an explicit, revision-guarded recovery command for
the exact session and turn. When a later owner revision removes that approval,
shared mode clears the frozen red status even if the session is still uncertain.
The map reports `statusEvidence: "uncertain"` on that task; the transition does
not resume pulses or comets. Recovery changes only monitoring state. It does not
approve or deny a Codex permission. A newly observed approval can make the task
red again. Source delivery alone does not change an installed bridge or lights.

`shared-status` and the Python `shared_input.inspect` function are pure local
reads. They report selection, neutral owner/consumer IDs, connection, last
revision/receipt time, evidence age, read capability and fixed error codes.
They do not poll, migrate state, refresh Codex metadata, launch workers, or command
lights. Tokens, token paths, local titles and private roots are excluded. The
future integration-settings API can consume this projection. No new dashboard
or wall-map controls are introduced here.

## Verification

Run `python3 scripts/check.py`, `npm run test:browser`, `npm run check:workflow`
and `npm run test:workflow`. Shared tests include the released fixture corpus,
archive byte checks, actual released-owner new-turn behavior, synthetic HTTP,
cutover/rollback, stale rendering, private inspection and retained forwarding.

`python3 scripts/measure-shared.py --output /tmp/shared-consumer.json` measures
900 synthetic Linux operations across repeated 1/10/50-session profiles. It uses
private disposable state, an authenticated fake loopback host and pure effect
construction. The checked receipt in `docs/performance/gh29-shared-consumer.json`
identifies source hashes. It is consumer overhead evidence, not the full-hook
baseline, final Hub #30 integrated performance qualification, Windows timing,
installed-client acceptance or optical evidence. Those gates retain their owners.
