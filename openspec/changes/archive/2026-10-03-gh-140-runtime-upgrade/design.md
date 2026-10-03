## Context

The accepted contract is published at Hub revision
`96710bba52054c381035a6afabe8348d2b9bbd93` (contracts 1.2.0).
The existing installation has three independently started services and detached
per-device workers. Its shared runtime parent also contains Hub and shared Node.
The implementation follows ADR 0016's acyclic owning modules.

## Goals / Non-Goals

The command upgrades the complete owned Python, MCP and vendor payload. It
preserves all mutable state and the established service, hook and executable
paths. It does not enroll devices, run previews, change modes, update shared Node,
install a scheduler or create a shared installer framework.

## Decisions

- Keep the source CLI in `install_linux.py` and put release/operation helpers in
  owning modules. Retain the existing fresh-setup argument form. The installer
  validates contracts 1.2.0 independently of the controller's 1.0.0 artifact.
- Build from the exact clean merged source in isolated disk-backed staging.
  Package every copied module, vendor artifact and MCP dependency; record trusted
  source/archive/manifest hashes and reject unknown, changed or unlisted content.
  Current selection is one `current` anchor, never separate component switches.
- Preserve the shared Python interpreter and environment. Stage pinned binary
  wheels into each target bundle's `bridge/python-deps`; include the closure in
  the immutable inventory and select it in the entrypoint and qualification
  probes. Previous code keeps its own dependency path or the unchanged legacy
  environment. Verify both closures and refuse unknown dependency compatibility
  before outage. No in-place pip upgrade or source distribution build is allowed.
- Qualify the established pre-diagnostics installation against PR #209 using
  the exact normalized product-module fingerprint pair plus dependency and
  target-write/previous-reopen probes in both directions. Other differing
  fingerprints still refuse. Matching code never assigns an unknown legacy
  installation a guessed source revision.
- Legacy admission needs a kernel-enforced boundary because old entrypoints know
  no new lock. Persist original directory modes/inodes before temporarily denying
  traversal of strictly owned bridge/MCP program directories. Require the ordinary
  non-root owner with no permission-bypass capability. Stop named units, drain
  identity-matched supported entrypoints and acquire each device's existing SQLite
  worker lock before copying state. A single quiet process scan is insufficient.
  Entry points opened before fencing must drain; interrupted fencing remains an
  explicit inspection barrier with exact restoration evidence.
- Preserve original legacy bytes and dependency closure. Introduce component
  forwarding links while fenced; only later `current` switches are atomic.
  Recheck protected Hub/shared paths before outage and after recovery.
- Load release identity once in the serving process. Add a separate authenticated
  build-health response without adding fields to controller v1 snapshots. A CLI
  reading a database is not evidence of the server's running build.
- Qualification exercises target writes and previous-code reopen in isolated
  state. Program rollback keeps the latest database and JSON state. Unknown
  compatibility refuses. Consistent backups are evidence, never automatic restore
  inputs. Operation intent and terminal receipts use fsync and exact readback;
  finalization failure is not success.

- The supervisor bridge accepts only a strict stdin request and a private trusted
  configuration naming the owner, installation, source, units, native npm and
  evidence root. It runs the native exact plan/operation, retaining a minimum
  600-second transition/recovery reserve before durable intent. Once switching
  starts, it reaches the native safe boundary without deadline cancellation.
  Reconcile is inspection only under the native shared lock: validate the full
  receipt, latest selected release, process/build identity and fresh health.
  Unresolved barriers or incomplete readback remain uncertain. Installation does
  not imply client, physical or issue acceptance.
  Verified native refusal or rollback may instead settle the failed attempt with
  fresh baseline health and complete legacy/release identity, leaving the selected
  issue parked without holding unrelated deliveries. This never repeats a switch.

## Risks / Trade-offs

- Unsupported direct Python imports or privileged writers can bypass ordinary
  entrypoint fencing: the planner refuses unsupported ownership and the procedure
  requires named supported entrypoints; it cannot claim arbitrary-process control.
- Existing code may lack trustworthy source/build metadata: retain explicit
  legacy identity and verify restarted processes plus served artifacts.
- Interrupted multi-component adoption needs inspection: keep original paths,
  modes, intent, receipts and locks instead of attempting an automatic second
  migration.
- Wall/controller startup may resume existing device behavior: the coordinator
  assesses that effect under the owner's authority before execution. Source tests
  use fake transports; no physical preview is part of upgrade health.

## Migration Plan

Before live use, run the read-only plan against the named established target,
review complete included changes, exact ownership, dependency compatibility,
admission and recovery. Stage and qualify before any outage. Under the lock,
persist intent, fence/drain, back up, convert owned paths and select the target.
Restore admission and restart only the recorded units; verify process identities,
wall/controller/MCP reads and retained state before a durable success receipt.
On eligible failure, repeat the fenced transition to compatible previous code
and verify recovery without restoring old state. Incomplete conversion or failed
recovery retains an inspection barrier.
