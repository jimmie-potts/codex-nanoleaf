# Linux installation

Run the existing Nanoleaf processes in Linux with private Linux SQLite state and
one light-writing worker per registered device. The wall map, controller API and Node MCP host are
separate services. Hooks and CLI commands update the same state and start the
worker when needed. Windows can still run Codex Desktop and the browser.

[Issue #54](https://github.com/jimmie-potts/codex-nanoleaf/issues/54) owns source
support. [Issue #55](https://github.com/jimmie-potts/codex-nanoleaf/issues/55) owns
the installed WSL, real-client and physical checks. See the
[ownership decision](decisions/0007-linux-runtime-ownership.md) and
[runtime specification](../openspec/specs/linux-runtime/spec.md).

## Prepare the host

Use ordinary Ubuntu WSL with Linux Python 3.12 or newer, Python venv/pip support,
native Linux Node 24 and npm. Setup downloads the locked dependencies. User
systemd operation must work in the ordinary WSL terminal; foreground commands
are available when a service manager is unsuitable. Runtime availability follows
WSL's lifetime. This project adds no Windows startup launcher or always-on host;
[ADR 0011](decisions/0011-runtime-availability-follows-wsl.md) records that
choice and defers hosting off WSL to the hub. The user units start with the
installing user's session, for example a WSL terminal; whether a Codex Desktop
task running in WSL starts them has not been measured.

Before setup registers active hooks, make sure no other Nanoleaf worker, map,
controller or MCP process controls the device. Preserve unrelated applications,
hooks and Codex data. Two workers must never control the device concurrently,
even if their databases are separate.

The fresh installation imports no old tasks, preferences, credentials or scene
state. Old Nanoleaf data may remain unused. No backup, data migration, rollback
tooling or soak period is required.

## Upgrade and roll back the installed runtime

The guarded commands implement the published
[install contract at `96710bba52054c381035a6afabe8348d2b9bbd93`](https://github.com/jimmie-potts/agent-device-hub/blob/96710bba52054c381035a6afabe8348d2b9bbd93/docs/install-contract.md),
using its independently pinned contracts 1.2.0 receipt validator. The controller's
wire contract remains 1.0.0. An authorized delivery includes routine installation
on the owner's established target after merge and main CI. Review the exact plan
under that standing authority; no repeat approval is needed. New installations,
hooks, agent-session changes, unqualified migrations and physical checks retain
their own boundaries.

Run the source command from a clean checkout that contains the merged revision.
Refresh Git refs before planning. Use the installation's unchanged Python with
its pinned controller dependencies and native Node 24/npm. Name the established
Linux state path explicitly; never select a guessed device or a Windows database.
Keep plan and receipt output private because it contains installation paths and
process identities, although credentials and state contents are excluded.

```bash
umask 077
python3 bridge/install_linux.py plan <full-merged-sha> --state-dir <installation> > <private-plan.json>
python3 bridge/install_linux.py upgrade <full-merged-sha> --state-dir <installation> --plan <private-plan.json>
python3 bridge/install_linux.py status --state-dir <installation>
```

`plan` and `status` make no installation, service or device changes. The plan
binds the source archive, installed inventory, configuration hashes, unit
commands, protected paths, complete commit comparison when known, outage and
recovery. Legacy comparison and unavailable PR attribution remain unknown.
Changed bound inputs require a fresh plan; routine changes within standing scope
do not need renewed human approval. Status separates the selected bundle,
running process/build evidence and remote main. An inactive controller has no
running build. A failed remote lookup leaves the comparison unknown.

The supported layout has three established, active user services:
`codex-nanoleaf-wall`, `codex-nanoleaf-controller` and `codex-nanoleaf-mcp`.
Their executable and argument paths must match fresh setup, with no additional
drop-ins or service effects. The ordinary installation owner and running
processes must lack DAC-bypass capabilities, and the selected executables must
have no privilege-elevating mode or file capability. The installer refuses
unsupported ownership, partial migration and unresolved prior operations.

The candidate contains every bridge Python module copied by fresh setup, wall
assets, both vendor trees, MCP source, build output and locked dependencies.
Staging uses the exact Git archive and disables npm lifecycle scripts. It never
updates shared Node or modifies the existing Python environment. Both previous
and target Python requirements must already pass in that environment. Build
duration and the selected Python strategy are recorded in private evidence.
Dependency changes require a separately qualified environment transition.

Rollback qualification requires the known durable implementation fingerprint,
an isolated target-write/previous-reopen fixture and unchanged reopening of a
consistent copy of current state by both programs. Unknown durable code or a
migration refuses before outage. This bounded qualification must be refreshed
when durable behavior changes; it does not promise every future source revision
can be installed automatically.

Before the first legacy adoption, verify that every writer uses the established
launcher, hooks or user services and the owned `bridge.py` / `mcp/dist/main.js`
entrypoints. Arbitrary embedded imports, alternate runtime copies and privileged
writers are outside this procedure. No hook configuration is modified. The
temporary fence removes directory search permission from only the owned bridge
and MCP directories, so even relative entrypoint opens cannot pass it. New hook
or CLI invocations can fail during this bounded outage. Existing entrypoints,
including processes that opened their script before the fence, are drained by
UID, argv path, start ticks and pidfd before device worker locks are acquired.
The plan and exact target must qualify this procedure before live use; a quiet
process scan alone is insufficient.

The operation holds its installation lock, writes and fsyncs an in-progress
receipt and active-operation barrier, records original directory modes, inodes
and hashes, fences admission, stops the named services and drains their workers.
Only then does it hold every device SQLite lock and copy durable state and
configuration. The SQLite backup is consistent; sockets and transient journals
are excluded. Credentials stay in private backups and never enter receipts.

First adoption retains original bridge/MCP/vendor directories under
`legacy/<legacy-id>`, with explicit unknown source identity. It creates stable
`runtime/bridge`, `runtime/mcp` and `runtime/vendor` links through one `current`
anchor. The `runtime` parent remains a directory; `runtime/hub-gh30`, shared
`runtime/node` and `.venv` remain unchanged. Component conversion occurs while
fenced and is not atomic. Each later `current` publication is one atomic rename.
An interrupted first conversion leaves the originals, fence records and active
barrier for inspection and blocks automatic replay.

After publication, the command restores admission, restarts only the named
services and checks bounded process-start/identity evidence, the served wall
artifact, `/api/state`, authenticated controller build/reads and authenticated
MCP discovery. It calls no device command or MCP tool. Service startup can resume
existing device behavior; assess that effect under the installation's authority.
These checks do not establish physical appearance or a real Codex client session.

If the candidate fails, recovery repeats the fence and writer drain, selects the
already-qualified previous code and reopens the latest durable state. It never
restores the pre-upgrade database. A healthy recovery is `failed-rolled-back`,
so the original upgrade still fails. Failed recovery remains an inspection
barrier. A healthy target is successful only after a schema-valid final receipt
has been atomically written, fsynced and read back. Finalization failure emits an
attempted `receipt-finalization-failed` document on stderr; that document does
not prove the on-disk receipt changed. Retention runs only after durable success
and preserves current plus three previous successful owned releases. Legacy
copies, receipts, backups, unknown directories and other-owner history are kept.

To select the last successful operation's verified recovery target:

```bash
python3 bridge/install_linux.py plan --operation rollback --state-dir <installation> > <private-rollback-plan.json>
python3 bridge/install_linux.py rollback --state-dir <installation> --plan <private-rollback-plan.json>
```

An explicit full SHA selects an already-retained, verified release. Rollback is
planned and qualified under the same authority and preserves newer state. There
is no force option, blind retry or automatic backup restoration. For an unresolved
operation, inspect the private receipt, `upgrade-records/active.json`, recorded
fence modes/inodes, actual links and processes first. Do not delete the barrier
or restore a mode onto a replacement inode. A reviewed recovery must name the
exact retained original paths and account for newer state before resolving it.
The command does not automatically repair a partially converted layout.

Report merged source, exact packaged artifact, installed receipt, running health,
client acceptance and physical acceptance separately. Source tests alone leave
installation pending.

### Shared supervisor adapter

The reviewed owning bridge is `bridge/runtime_adapter.py --config <private-json>`.
It accepts one JSON request on stdin and emits one JSON response. Configure its
fixed argv in the supervisor; never construct shell commands from issue text.
The private configuration has exactly these fields:

```json
{
  "schemaVersion": 1,
  "owner": "jimmie",
  "stateDirectory": "/absolute/established/nanoleaf",
  "sourceRoot": "/absolute/clean/reviewed/source",
  "systemdDirectory": "/absolute/user/systemd/units",
  "npm": "/absolute/resolved/native/npm-cli.js",
  "evidenceRoot": "/absolute/private/supervisor/evidence",
  "transitionReserveSeconds": 600
}
```

These are placeholders, not a qualified installation. The coordinator binds the
actual paths and named owner during activation. Configuration is an owned private
regular file; paths are absolute, existing and free of symlink ancestors. State
and evidence directories are private. Source and unit directories are owned and
not writable by other users. The native npm path is an owned executable regular
file: resolve an npm symlink before recording it. The supervisor pins the reviewed
Python executable, configuration, adapter and imported owning module/receipt
artifact closure using its existing `files` fingerprints. Updating those pins or
the running supervisor's adapter waits for its stopped ownership boundary.

The strict request uses the shared supervisor protocol:

```json
{"schemaVersion":1,"operation":"install","repository":"jimmie-potts/codex-nanoleaf","issue":140,"merge":"<full merged SHA>","owner":"jimmie","deadline":1234567890,"evidenceDirectory":"<private child of evidenceRoot>"}
```

Unknown fields, duplicate JSON keys, changed authority and evidence outside the
configured root refuse. Install saves and reads back the native exact plan, then
passes that plan to the same native operation. The bridge reserves at least 600
seconds for switching, health and recovery, caps preflight subprocess calls to
the remaining preparation time, and rechecks the reserve immediately before
durable intent and fencing. Slow preparation refuses before outage. Once a
switch starts, neither deadline nor supervisor pause cancels it; native recovery
reaches its safe boundary. A deadline overrun remains unaccepted by the supervisor
until inspection. This reserve does not promise a deadline for stalled kernel or
storage I/O. Configure the supervisor timeout and reserve to accommodate the
owning operation rather than wrapping it in a process-killing timeout.

`operation: "reconcile"` only inspects. Under a shared native installation lock,
it validates the complete semantic receipt, exact selected bundle and requested
revision, then obtains fresh running process/build and wall/controller/MCP health
readback. It never stages, installs, rolls back, starts services, removes a
barrier or repeats an ambiguous operation. Evidence is written only in the
request's private evidence directory. Missing or inconsistent proof and any
unresolved active barrier return `status: "uncertain"`.

Only complete readback returns `status: "installed"`, the exact repository,
merge and owner, matching `installedRevision` and `runningRevision`,
`health: "healthy"`, and the retained native `receipt: {path, sha256}`. A native
`migrate` receipt can qualify the first adoption; `failed-rolled-back` cannot
qualify the requested upgrade. This adapter establishes installation only.
The separate owning closeout procedure still checks client, physical and all
other issue acceptance before closure.

## Install from the reviewed checkout

Record `git rev-parse HEAD` with the #55 acceptance evidence. From that checkout:

```bash
read -r -p 'Nanoleaf private IPv4 address: ' NANOLEAF_IP
python3 bridge/install_linux.py --ip "$NANOLEAF_IP"
unset NANOLEAF_IP
```

Paste the device token at the hidden prompt. For unattended preparation,
`--token-file /private/path/device-token` reads a token-only regular file. Keep
that file private. Do not put the token in a command argument, repository,
screenshot or issue. Setup validates device layout with a read request; it sends
no light write and starts no service or worker.

Setup defaults to `~/.local/share/codex-nanoleaf`, creates it with owner-only
permissions, and keeps its SQLite databases, credentials, copied runtime and
Python virtual environment there. The selected Node executable is also copied
into that installation, so services do not depend on the source checkout.
`--state-dir` can choose an empty directory on a supported local Linux filesystem,
such as WSL's ext4. Mounted Windows, network and unrecognized filesystem types
are rejected, including resolved symlink destinations. Never place
runtime databases under `/mnt/c`.

`config.json` also registers each device under `devices`; the original Lines
device is `wall` and its token stays under `token`. `layout.json` holds one
entry per device. When newer source opens an existing installation's database,
the [device state specification](../openspec/specs/device-state/spec.md) upgrade
adds the device key in place and preserves tasks, preferences, pending edits,
the active comet and controller history. The same upgrade runs wherever this
source opens a database; only this Linux path is qualified.

The installer replaces only entries with this integration's hook marker and
preserves unrelated handlers and settings. By default it uses
`$CODEX_HOME/hooks.json`, or `~/.codex/hooks.json` when `CODEX_HOME` is unset.
Use `--hooks-file /path/to/hooks.json` to select the actual Codex home, repeating
the option for separate clients. These commands require tasks executing in WSL;
review and trust the new hooks in the client. A hook registered in the Codex
Desktop home on the Windows drive carries the same Linux command and fires only
for tasks that run in WSL; native Windows tasks are not monitored. Registration alone does not prove
that the installed client's sandbox can run them or launch the worker.

For a shared-input cutover, select shared input first, then remove the legacy
Nanoleaf hooks separately from the WSL CLI and Windows Desktop homes:

```sh
nanoleaf shared-select shared
nanoleaf hooks remove --codex-home "$HOME/.codex"
nanoleaf hooks remove --codex-home /mnt/c/Users/ACCOUNT/.codex
```

Hook removal changes only entries carrying this integration's marker and keeps
a private backup. It refuses while legacy input is selected. To roll back,
register the hooks in each Codex home first, then run
`nanoleaf shared-select legacy`. Registration retains the installation's state
directory in new hook commands. Legacy selection refuses when the configured
Codex home lacks a marked handler for any legacy event and directs the operator to `hooks register`.
These commands do not change device mode, tasks, or physical device state.
Registration keeps existing handler positions and restores the original file
on an unchanged remove/register round trip. If unrelated edits intervene, it
preserves those edits and restores missing handlers from the backup. After
either operation, restart each affected Codex client and review required hooks
marked new or modified. Removal can also shift retained shared hooks to a
different trust entry. Verify a fresh prompt through the selected input before
accepting cutover or rollback; a hook file or healthy feed is insufficient.

The existing metadata readers accept explicit mounted paths:

```text
--desktop-state-path /mnt/c/Users/ACCOUNT/.codex/.codex-global-state.json
--metadata-path /mnt/c/Users/ACCOUNT/.codex/.codex-global-state.json
--title-index-path /mnt/c/Users/ACCOUNT/.codex/session_index.jsonl
```

Replace those examples with the files used by the installed Desktop client.
`--metadata-path` defaults to `--desktop-state-path` when supplied. Unavailable
or malformed files retain the readers' existing conservative behavior. The
runtime only reads these files; it never writes Codex's database or marks tasks
read. Mounted JSON is allowed, while shared mounted runtime SQLite is not.

Other options are `--node`, `--npm`, `--systemd-dir`, `--wall-port`,
`--controller-port` and `--mcp-port`. Choose three distinct ports from 1024 through
65535. Setup refuses a nonempty state directory or existing Nanoleaf unit files.
If preparation fails, inspect the reported step and select an empty project
directory for a fresh retry. Existing installations use the guarded upgrade
procedure above; fresh setup is never an upgrade or rollback step.

## Run the services

The default user units are written to `~/.config/systemd/user`. Run these
commands in ordinary WSL:

```bash
systemctl --user daemon-reload
systemctl --user enable --now codex-nanoleaf-wall codex-nanoleaf-controller codex-nanoleaf-mcp
systemctl --user status codex-nanoleaf-wall codex-nanoleaf-controller codex-nanoleaf-mcp
```

Each unit runs a foreground process with a private umask and restarts on failure.
The worker stays on demand. Each registered device has its own instance and
exclusive SQLite lock, and the Lines keep the existing lock file.
For foreground operation, run each command in its own terminal, with the matching
user service stopped:

```bash
~/.local/share/codex-nanoleaf/nanoleaf serve
~/.local/share/codex-nanoleaf/nanoleaf controller-serve --port 41231
~/.local/share/codex-nanoleaf/runtime/node/bin/node \
  ~/.local/share/codex-nanoleaf/runtime/mcp/dist/main.js \
  --config ~/.local/share/codex-nanoleaf/mcp-config.json
```

Use the chosen state directory and controller port for a customized installation.
Default endpoints are:

| Service | Endpoint |
| --- | --- |
| Wall map | `http://127.0.0.1:8765` |
| Controller | `http://127.0.0.1:41231/controller/v1` |
| MCP | `http://127.0.0.1:41230/mcp` |

All listeners bind numeric loopback. A configured occupied port fails; it does
not silently select a replacement. Check the named unit's journal with
`journalctl --user -u codex-nanoleaf-wall` or the corresponding controller/MCP
unit. Stop the port's owner or choose another port in private configuration and
the unit's command; keep MCP's controller port in sync.

```bash
~/.local/share/codex-nanoleaf/nanoleaf status
~/.local/share/codex-nanoleaf/nanoleaf map --no-open
~/.local/share/codex-nanoleaf/nanoleaf mode work
~/.local/share/codex-nanoleaf/nanoleaf mode quiet
~/.local/share/codex-nanoleaf/nanoleaf mode free
```

The map command verifies or starts this installation's map and prints its URL.
It never launches a browser on Linux. Open that URL in the Windows browser and
verify reachability during #55. The page keeps its existing controls and
Host/Origin/edit-token protections. The browser never receives the device token.

Mode commands use existing Work/Quiet/Free behavior. Free releases light control
according to the current scene policy. CLI and controller status describe
desired state, pending work and transport evidence; they do not prove visible
light output. Stopping a listener does not cancel work already owned by the
worker. Stop the services and active worker when retiring this installation.

## Add NL22 Light Panels

Enroll original NL22 Light Panels beside the Lines with the installed launcher.
Enrollment never runs fresh setup, clears tasks or changes hooks, listeners or
machine credentials. It verifies the device before it writes anything:

```bash
read -r -p 'Light Panels private IPv4 address: ' PANELS_IP
~/.local/share/codex-nanoleaf/nanoleaf device-enroll --ip "$PANELS_IP"
unset PANELS_IP
```

Paste the Panels credential at the hidden prompt, or pass `--token-file
/private/path/panels-token` as with Lines setup. To obtain a new credential from the
device instead, add `--pair`. The command asks you to hold the Panels' power
button for 5 to 7 seconds until the lights flash, then press Enter. The device
id defaults to `panels`; choose another with `--device <id>`. The command
refuses `wall`, an address another device already uses, and an existing id at a
different address. Repeating it for the same id and address replaces only the
credential and keeps the device's mode, layout and reservations. Enrollment never
changes a registered address.

If the Panels get a new address, for example after a new DHCP lease, move them
without re-enrolling:

```bash
read -r -p 'New Light Panels private IPv4 address: ' PANELS_IP
~/.local/share/codex-nanoleaf/nanoleaf device-address --device panels --ip "$PANELS_IP"
unset PANELS_IP
```

The command asks the device at the new address, with the stored credential, to
report NL22 Light Panels with the saved triangles in the same places. It refuses an address another
device uses, a different device and an unreachable address, and then changes
nothing. On success it changes only the registered address. The Panels keep their
id, mode, layout, reservations and saved scene, and no light write is sent. No
service needs a restart: a running worker sends to the new address from its next
pass. The command moves registered Light Panels only; it refuses the Lines
device `wall`.

The new device starts in Free and receives nothing until you activate it.
Activation shows only current task status; it replays no earlier wave or comet:

```bash
~/.local/share/codex-nanoleaf/nanoleaf mode work --device panels
~/.local/share/codex-nanoleaf/nanoleaf status --device panels
```

No service needs a restart. Hooks and the worker read the device list each time
they start, and the map reads it on every state request. The controller and MCP
reach the Panels only after you
[add them to the controller](controller-api.md#add-the-nl22-light-panels). The map opens on the Lines; once a second device is
registered, its **Device** control beside the wall heading switches the page to
the Panels, and `?device=panels` in the map URL opens it there directly.

To remove the Panels, hand them back first and wait until status shows nothing
pending, so they restore their own scene:

```bash
~/.local/share/codex-nanoleaf/nanoleaf mode free --device panels
~/.local/share/codex-nanoleaf/nanoleaf status --device panels
~/.local/share/codex-nanoleaf/nanoleaf device-remove --device panels
```

Removal stops that device's worker and deletes its registration, credential,
layout entry, saved state and scene. Lines and shared tasks are unchanged. Add
`--force` only for an unreachable device whose Free handoff cannot finish; its
lights then keep what they last showed. If its worker is still stopping, the
command says so, and running it again finishes the cleanup.

Source tests use temporary state and fake devices. They are not evidence that
enrollment worked on the installed runtime or that the Panels lit up.
[#46](https://github.com/jimmie-potts/codex-nanoleaf/issues/46) owns that
installation and physical check.

## Connect MCP

Setup configures the direct loopback HTTP transport, `loopback-http`. An
installation whose `mcp-config.json` still names `windows-http` is accepted as
the same transport. No helper process is involved.
`mcp-credentials.json` contains a private controller credential and the digest
of a separate MCP bearer. `mcp-client-token` holds that client bearer. Keep both
files private and give the client only the MCP bearer.

Use the existing [Codex MCP configuration instructions](local-mcp.md#configure-and-inspect-codex)
with `http://127.0.0.1:41230/mcp`. Supply `NANOLEAF_MCP_TOKEN` privately in the
selected client's environment from `mcp-client-token`. Verify status before a
mode command. Mode requests retain the controller's request ID, revision,
generation, authentication and uncertainty rules.

## Installed acceptance

In #55, record service, actual client, HTTP/MCP transport and visible-light
results separately. Verify one real WSL task, its hooks and metadata, the Windows
browser, authenticated mode commands, and a bounded Work/Quiet/Free sequence.
Record the final mode and scene. Reopen WSL and check startup again. Document
any client permission or systemd limitation without treating source tests as
installed evidence. [Hub #43](https://github.com/jimmie-potts/agent-device-hub/issues/43)
tracks the corresponding architecture and maintained-guide synchronization.
