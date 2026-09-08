# Local Codex acceptance, 2026-09-08

The repository owner completed the authorized Windows upgrade and local Codex
acceptance for [issue #34](https://github.com/jimmie-potts/codex-nanoleaf/issues/34).
Both native Windows and same-machine WSL Codex controlled the installed Windows
bridge. The owner observed Work, Quiet, Free and restoration to Work. Temporary
MCP access was revoked and the ordinary Windows app remained operational.

This record separates synthetic failures, real controller receipts, device
readback and human observations. It does not qualify shared monitoring, remote
clients, arbitrary brightness or scenes, physical fault injection, or a soak.
The issue and its evidence PR own delivery status and PR/main validation.

## Versions, authorization and installation

| Item | Tested value |
| --- | --- |
| Installed/source candidate | `3f2f33ab1d19db75b613943f7948ff44c7bc6ddc`, including the separately delivered wall-map UI |
| MCP source delivery | `bdc78620c2e839c3e44cfd4d4a22f8ae4d9b8279`, [#33](https://github.com/jimmie-potts/codex-nanoleaf/issues/33) |
| Shared MCP artifact | `device-mcp-v1.0.0`, source `06c9c504a107cc04093c34500dadbbc6082679d2` |
| Actual Codex clients | CLI `0.153.4`, native Windows and WSL |
| Node | Windows `24.19.0`; WSL `24.20.0` |
| Windows Python helper/installation | `3.12.14` |
| Device | Nanoleaf Lines, model `NL59`, firmware `12.3.2` |
| Upgrade | 2026-09-08, 04:38:50-04:38:59 UTC |
| Completed physical run | 2026-09-08, 05:37:43-05:43:12 UTC |

The repository owner supplied the exact configured device address privately and
explicitly approved setup, temporary Codex sessions, backup/rollback and the
bounded mode sequence. The configured target matched before installation and
physical testing. Addresses, credentials, process IDs, task metadata, private
paths and raw client transcripts are excluded from this record.

The supported Windows installer backed up program files and private state,
verified backup database integrity, and restarted only the existing
installation's tray, map server and worker. It preserved existing shortcuts.
All 37 checked bridge source files matched the candidate; installed program
comparisons passed. Both MCP runtime copies matched all 24 tracked package files.
No fresh setup or task reset was used.

Upgrade comparisons preserved the ten checked task tables, preferences, pulse
epochs, scene state, layout, configuration, hooks and Codex settings. The
rollback plan retains the current database and newer tasks while restoring
backed-up program files. No rollback was needed. Initial Work was powered on at
30% brightness, with no saved named scene. Restoration could recover the current
Work task display, but not an unknown earlier scene or exact animation frame.

## Actual clients with synthetic controllers

Before the physical run, both installed Codex clients exercised the delivered
MCP host against a synthetic Windows HTTP controller. WSL used the supported
Windows Python helper. Discovery exposed exactly `nanoleaf_status` and
`nanoleaf_mode_set`; their read-only annotations were respectively true and
false. Discovery and status caused no fixture writes. Modes were Quiet, Work,
Free and Work, with nine tool calls per positive sequence. Brightness remains a
mode policy; no standalone brightness tool is advertised.

Each client also completed a three-call stale-revision case. The controller
returned `revision-conflict`, no prior effects and `never-automatically` retry
policy. The subsequent status showed unchanged mode, generation and next
request identity. The first Windows negative attempt used unsupported status
arguments and stopped before controller effects; the corrected focused attempt
passed. It is not counted as a passing stale-revision test.

Separate read-only sessions on each client reported `approval: on-request` in
their actual startup headers. This records the selected policy, not an
interactive approval prompt for every write. Tool classification and successful
execution alone do not establish prompt presentation. Test credentials were
revoked with HTTP 401 readback and owned fixture processes were stopped.

## Installed routes and physical observations

Windows Codex used the Windows MCP host and installed Windows controller API.
WSL Codex used the Linux MCP host, Windows Python HTTP helper and that same API.
Neither MCP route opened SQLite or created a light worker. The existing Windows
worker remained the sole device writer alongside the ordinary map and tray.

The completed run used six actual Codex sessions: one read-only policy/status
session per route, followed by four status/mode/status sessions. That is 14 tool
calls and four fresh mode requests. Each policy read left controller command
state unchanged. Both selected policies were `on-request`.

| Request | Receipt/transmission | Separate device readback | Owner observation |
| --- | --- | --- | --- |
| Windows Work | Completed no-op, `cancelled`, `priorEffects: none`, zero transport operations | Power on, 30%, dynamic effect | Original Work task display remained |
| Windows Quiet | `queued` then `sent`, two completed transport operations, none uncertain | Power on, 10%, static effect | Task colors became steady and dimmer |
| WSL Free | `queued` then `sent`, two completed transport operations, none uncertain | Power on, 30%, static effect | Blue except one green half-Line; task pulsing stopped |
| WSL Work | `queued` then `sent`, two completed transport operations, none uncertain | Power on, 30%, dynamic effect | Normal Work task display and original brightness returned |

Each visual observation lasted at least five seconds. Initial and restored Work
also included owner confirmation of the ordinary app display. There were no
uncertain terminal receipts. `sent` establishes transmission; the separate
readback and owner observations establish the limited physical result above.

The Free prompt incorrectly predicted uniform blue. The owner's exact observation
was: "There Is one green light of one half of one of the lines. Everything else
is blue." The owner subsequently confirmed that the green half was steady and
task pulsing had stopped. Existing project rendering retains project signature
colors in the no-scene fallback while clearing task animation. An isolated
worker exercise with a synthetic green project reproduced one steady green half,
29 blue halves, 30% brightness and no further light requests on a task event.
This supports the observation; it does not identify the private live project's
mapping or claim an all-blue display. See the [mode guide](../bridge/README.md).

## Ownership, replay, recovery and cleanup

The ordinary tray, map and worker processes were identical before and after the
physical run. Map health passed. All ten compared task tables were unchanged,
no preexisting task was lost and no unchanged task's pulse epoch changed. Scene
state, preferences, configuration, layout, hooks and Codex settings were
preserved. No helper bypassed the Windows queue with direct device writes.

An explicit duplicate of the completed Work no-op returned HTTP 200 and the same
receipt without changing controller command state. Each actual client session
then closed and its MCP host stopped before the next session started. Reopening
the route used current status and the next request identity. No automatic
request retry was observed. This checks bounded disconnect/reconnect between
completed calls; it does not test disconnection during a physical transmission.

Worker failure/restart, uncertain dispatch and recovery were exercised with
isolated source fixtures in `tests/test_controller_worker.py` and
`tests/test_controller_state.py`. These verify that uncertain work remains held,
restart does not retransmit old attempts, explicit new intent can recover, and
revoked unsent work cannot fall through to legacy writes. MCP transport fixtures
retain uncertainty and request identity on failed delivery without retrying.
No live worker outage or network interruption was performed or authorized.

After restoration, both dedicated controller credentials and all session MCP
credentials were revoked and rejected with HTTP 401. Owned MCP hosts and the
temporary controller listener stopped; their ports were no longer listening.
Plaintext acceptance credentials were removed. The existing controller identity
and private ledger were retained. No persistent Codex MCP entry was installed.
The ordinary Windows app remained in Work, powered on at 30%, with no pending
mode request or reported error. Cleanup recorded no errors.

## Earlier stops and configuration accounting

- Native Windows startup initially timed out with disposable Codex state.
  Normal client-managed state exposed a Windows sandbox selection error.
  Selecting `windows.sandbox="elevated"` for the test invocation allowed it to
  run. Existing unrelated MCP entries were disabled only for each invocation.
- The first physical attempt stopped at the initial observation prompt because
  the helper required a literal input prefix. It issued no mode request. The
  input helper was corrected; this was not evidence of a light failure.
- The next attempt completed one Windows read-only call, then stopped because
  the saved Codex settings file changed during client startup. A trusted-project
  entry for its temporary working directory was present afterward. The original
  byte-level delta was not retained, so the exact changed keys and writer cannot
  be established retrospectively. The owner reported no manual settings change.
  Cleanup restored ordinary app continuity without any mode request.
- The completed run reused already-trusted working directories and retained the
  strict settings comparison. Native Windows and WSL settings remained
  byte-identical through their sessions; final installation comparisons also
  passed. This does not erase the earlier observed settings change.

The dated private results and the owner's observations were inspected for this
redacted record. Earlier stopped wrappers remain failure history. Only the final
completed run and the separately evaluated synthetic checks support the pass
claims here. Hosted CI and source tests are recorded separately in the evidence
PR under the owner's previously approved local PR/main validation exception.
