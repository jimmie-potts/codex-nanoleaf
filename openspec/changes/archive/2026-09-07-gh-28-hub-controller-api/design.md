## Context

See `proposal.md` for the motivation and linked issue. This change needs a design because it adds authentication, a dependency, durable admission, cross-process coordination and failure recovery.

Current source evidence establishes the following constraints:

- `bridge/wall_server.py:App.state` refreshes metadata, writes state, may discover geometry through the controller and may launch a worker. It cannot serve as a pure machine snapshot reader.
- `bridge/bridge.py:get_status` uses a read-only SQLite connection. `connect_state` initializes and migrates state and therefore belongs outside request reads.
- `set_mode` uses `BEGIN IMMEDIATE`, changes saved mode, clears obsolete mode effects and wakes the worker. `run_worker` holds the Windows worker lock and checks mode/event revisions before light sends.
- `render` fixes task brightness at Work 30% and Quiet 10%. `SceneRestorer` retains the user's scene and its brightness. There is no independent brightness policy to expose in this issue.
- Installed WSL command dispatch occurs before opening state. Existing source tests inject a clock, sender, scene factory and worker launcher.

## Goals / Non-Goals

Keep the machine boundary small enough to validate through actual HTTP and the existing worker. Persist admission and desired changes atomically, and expose uncertainty when a crash prevents proving what was sent.

This change does not add shared input reduction, a database owner migration, new scene/brightness controls, renderer previews, wall UI changes or installation into personal state. Source tooling may support later activation.

## Decisions

### Adopt the immutable shared package directly

Vendor the unchanged release archive and its extracted package content in a versioned dependency directory. Keep the shared Python package beside its schema in the original relative layout; it resolves the schema relative to its package path. Keep the package manifest, fixtures, README and source consumers for provenance and conformance.

The pin is `@jimmie-potts/device-contracts` version `1.0.0`, API `1.0`, source `589846bcbe6a4a06ef6aaec9d2952c9f9d58dac3`, private release `controller-contracts-v1.0.0`, archive `jimmie-potts-device-contracts-1.0.0.tgz`, SHA-256 `5e0b30ac92e6e8e1e38d8249b740b565de66e3cc810a04bc6fac23e182e84e87`. Record the actual release asset URL and receipt in the adoption record. Verify archive bytes and each manifest entry before import. Fail closed for a missing, altered or unsupported artifact.

The optional machine listener imports the shipped Python consumer, including its strict schema validator and pure admission/feed decisions. Declare `jsonschema==4.19.2` and pin its transitive controller dependencies for the supported Python matrix. Load these dependencies only on explicit controller enable/start. Legacy hook, mode, status, map and worker startup must still run without them. The worker's small persistence helpers use the standard library and do not import HTTP/schema dependencies.

CI installs controller test dependencies from this repository, runs all shared fixture IDs against the unchanged Python consumer, then exercises equivalent decisions through the owning API and queue. It does not fetch a mutable branch, import a sibling checkout, or require a new private cross-repository credential. Reimplementing the shared validator/admission algorithm would create an unnecessary compatibility burden; eager dependency imports would break legacy startup.

### Separate opt-in machine listener

Add `controller_server.py` for HTTP/authentication and `controller_state.py` for stdlib persistence, read projection and worker bookkeeping. Extend bridge CLI dispatch with explicit controller configuration, credential provisioning/revocation and listener start/status commands. Installed WSL variants forward to Windows before reading configuration or opening any SQLite file.

Use a separate loopback listener and private endpoint discovery record. Keep the existing wall server handler and browser token behavior. Recommended routes are `GET /controller/v1/devices`, `GET /controller/v1/snapshot?deviceId=<id>`, `POST /controller/v1/commands`, and `GET /controller/v1/feed?deviceId=<id>&epoch=<id>&sequence=<integer>`. Discovery returns only authorized configured targets. The feed returns a finite JSON array of shared feed events; persistent streaming is unnecessary for this delivery. Document these route wrappers because the shared package defines envelopes and HTTP errors, not these route names.

Store neutral operator-selected controller/device/source IDs and optional explicit label in separate private controller configuration. Do not derive them from the LAN address, paths, conversation titles or project names. Credentials are opaque random machine credentials mapped to a principal, target IDs and read/control scopes. Store only credential verification material where practical; reveal a newly provisioned credential only through the explicit local provisioning command. Client destination is private deployment configuration, never a command field.

Require the exact loopback Host including the bound port. Require bearer authentication on every route and before any cache lookup. Reject browser tokens. If supplied, Origin must equal this listener's origin and Fetch-Metadata must not indicate a cross-site request; absence of Origin never authenticates a client. Do not enable CORS. Revocation is immediate and is checked again on every feed request and before queued control starts. No overlap period is needed for the first implementation. Listener lifecycle/configuration changes are local operator commands, never generic control requests.

Advertise bounds of 65,536 body bytes, 32 admitted/in-flight requests, 32 pending requests, 256 retained completed receipts, 32 retained feed events and at most 16 concurrent feed clients. Apply a finite 2-second authentication/header/body read timeout and 5-second total request budget. Apply the admission semaphore before creating a request thread, reject oversized or malformed lengths and unsupported transfer encodings before body allocation, and close slow clients. Finite polling avoids an idle stream lifetime and backpressure queue. Test both parser rejection and contract capacity ordering.

### Preserve the supported mode policy

Advertise `modes:{supported:true,values:["Work","Quiet","Free"]}`. Advertise every required generic flag explicitly, with power, brightness, media, zones, scenes and preview unsupported. Convert only the wire mode casing to the existing internal mode names.

The shared snapshot's pending collection holds supported controller commands. It does not export private wall patch payloads. Existing reservation/layout edits stay owned by the wall editor. A browser mode change participates in the same controller revision/generation coordination, so a native client cannot overwrite a newer browser decision using an old snapshot. Relevant wall settings mutations also invalidate the shared configuration revision. Task metadata refreshes and ordinary pulse progression do not consume configuration revisions.

A same-mode command still follows admission/replay rules. If the mode is already applied and needs no work, complete it as `cancelled` with `priorEffects:none` and no failure. Never report `sent` without transport evidence. Existing failed/pending same-mode work still needs a worker retry and cannot take this shortcut.

### Commit admission and desired mode in one database transaction

Add prefixed controller tables to the existing Windows-owned `status.sqlite`; do not create a second independently committed command database. Keep request IDs, configuration revision, generation, bounded receipts, queue state, send-attempt state and feed events separate from sessions, task activity, unread receipts and comets.

Extract a transaction-level mode mutation helper from `set_mode`; retain the existing wrapper for tray/browser callers. Machine admission opens one `BEGIN IMMEDIATE`, refreshes authorization and the current controller state, invokes the shared admission function, reserves the request identity, saves its canonical request and queued/failed receipt, and applies the accepted desired-mode change within that transaction. Commit before waking the existing worker. SQL uniqueness and the transaction enforce one reservation across concurrent processes. A launch error after commit cannot erase the request or make a duplicate execute again.

Honor shared ordering. Authentication, shape, target, body bounds and identity checks precede admission. An identical cached body replays the retained receipt; an identical pending body joins that request. Changed bodies conflict. Expired/foreign epochs and future sequences reject without reservation. Capacity rejection consumes no identity. After reservation, stale revision, stale generation and unsupported capability failures are retained as that request's receipt.

The pure shared admission decision does not advance generation. After successful admission, the owning mode policy may advance it and stamps the new queue entry with the resulting execution generation, so that the request does not cancel itself against its pre-admission expectation. Use one independent controller generation to retire outstanding machine work when a newer mode decision supersedes it, including browser/tray decisions. Complete older queued requests as cancelled/stale-generation without sending. Increment configuration revision for accepted native desired changes even if the mode value repeats, as required by the shared admission result. Never reuse `activity.started`, `comets.started` or the existing animation event revision as the public generation or request counter.

### Journal possible effects before the worker sends

The existing worker remains the sole light writer. Machine server code can commit desired state and launch that worker; it cannot construct a Nanoleaf transport client or call render/scene methods.

Claim a queued request and durably record the intended bounded operation ID before a possible send. Immediately before each queued side effect, recheck current generation and authorization under Windows coordination. A stale entry cannot begin another send. Track scene brightness/selection and display sub-operations separately when one mode transition needs more than one transport request. Keep generation stable across one command's sub-operations unless a newer decision retires it.

Record successful transmissions with bounded operation IDs and a controller monotonic sample. Report `sent` as transport success only. Preserve successful sub-operations when a later one fails; use `partially-applied` or `uncertain` with the corresponding `priorEffects`. A timeout after a possible send must not report `none`. Keep the last known successful send through later errors.

A restart that finds a durable in-progress attempt with no committed result marks it uncertain with possible prior effects. It does not replay that machine request automatically. Retry after an uncertain outcome requires a fresh client snapshot and a new explicit request. Ordinary legacy worker reconciliation remains governed by the newest mode and existing effect epochs; it must not turn a recovered machine request into a second execution.

A worker launch failure or expired finite pending deadline becomes a typed failure with no claimed send when no attempt started. A fake clock and injected launcher prove recovery without sleeps or hardware. Revocation cancels unsent work for that credential; already attempted work retains its actual prior-effect evidence.

### Pure snapshot and bounded feed projection

Initialize/migrate controller tables at explicit controller startup or a writer path. HTTP reads use SQLite `mode=ro` and never call `connect_state`, wall metadata refresh, geometry discovery, `dashboard`, unread reconciliation, allocation, `current_comet`, worker launch or light transport. On missing/corrupt/unavailable state return a bounded service failure instead of silently creating a database.

Project only shared strict envelope fields. Desired mode comes from the saved mode; desired power/brightness and device observation remain unknown unless there is specific recorded evidence. Last update errors map to bounded typed codes. Do not return raw exception strings, configured addresses, secrets, wall tasks or paths. Service health describes the owning service, separately from device observation. Snapshot sampling may update its own sampleClock value but cannot refresh observation evidence or claim connectivity.

Append full shared snapshots to the finite event history when writers change public state, not when clients read it. Return later retained events in order. Invalid, future, expired or foreign-epoch cursors return one resync with the current snapshot. A current cursor returns no changes. Reconnect is read-only.

Keep stable configured IDs and durable request/feed history across ordinary restarts. A listener restart changes its sample clock epoch; old send evidence retains its original epoch and unportable observation freshness becomes unknown. Rotate controller/request/feed epochs only when the durable ledger is missing, reset or incompatible and continuity cannot be established; expire old request IDs while retaining any recoverable uncertainty for prior attempted work. Never compare counters from different epochs. Do not reset task/effect timestamps to align public clocks. Evidence from an old clock epoch must remain explicitly old/unknown instead of being rebased to the restart time.

## Risks / Trade-offs

- Optional Python dependencies add an activation prerequisite. Keep them behind the listener entry point, document the exact install command, and test legacy imports with dependencies unavailable.
- Existing light I/O can partly succeed before an exception. A durable attempt journal and typed partial/uncertain receipts avoid an unsupported exactly-once transport claim.
- Browser edits currently have no common command ID. Coordinate revision/generation in their existing write transactions and preserve their response shape; do not expose wall patches through the common command schema.
- The bridge may be intentionally idle in Free. Do not equate an absent worker process with device disconnection or issue controller health probes from reads.
- Holding a state transaction during a bounded send can delay another writer. Preserve the existing finite controller transport timeout, bound admission waits and test contention; do not introduce a second light writer to avoid it.

## Migration Plan

Add only prefixed tables/metadata through an idempotent migration and prove that existing sessions, waits, unread receipts, activity/comet epochs, slots, reservations, preferences and scene files survive unchanged. No fresh setup/reset is part of adoption.

Update source copying, backup and process lifecycle rules for the new modules and vendored dependency. Preserve private machine configuration and credential material in supported upgrades/backups without placing them in Git or ordinary API output. Disabling the listener leaves legacy behavior available. Rollback stops only this installation's controller listener and restores backed-up program files; it keeps current task state and disables machine access until a compatible version resumes. Older legacy code can ignore the new prefixed tables.

Source validation uses isolated state only. Windows installation, real native clients and physical-light acceptance belong to separately authorized verification. Update `docs/hub-integration.md`, `docs/development.md`, `bridge/README.md` and a local ADR to name contract ownership, opt-in dependencies, mode-only capabilities and evidence limits. The delivery coordinator performs repository validation, spec synchronization/archive and final review.
