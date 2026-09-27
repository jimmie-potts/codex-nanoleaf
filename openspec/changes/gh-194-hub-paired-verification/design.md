## Context

See proposal.md. The change widens the run's process boundary from "refuse everything" to "allow one loopback port". It also brings credentials into a run and adds a concurrent writer thread beside the map and controller listeners. Those meet the schema's design criteria for security and concurrency.

## Goals / Non-Goals

A paired run must reach the paired Hub's feed and nothing else. It must let the Hub reach the wall's real controller API, paint Hub-fed lifecycle state with the real projection, and let an orchestrator assert freshness and applied settings without a credential. It never sends a light request. Nanoleaf mode, power and brightness execution, comets, acknowledgment and restarting one consumer while paired are out of scope.

## Decisions

**One pairing convention, fixed in the wall.** Hub #495's orchestrator and Pixoo's #120 use the same values. They are the scenario name `hub-paired`, and the `hub-feed` input, the Hub run's origin `http://127.0.0.1:<port>/`. Two credential files go into the run's runtime directory: `hub-feed-token` and `hub-controller-token`, each holding one 43-character base64url token. The Hub owner is `verify-owner` and the consumer is `nanoleaf`. The qualified source is `{codex, cli, verify-host, verify-source}`. The controller identity is `wall-controller` / `wall` / `wall`, and the Hub's principal is `hub`. The owner is pinned in the shared-input configuration rather than learned from the first envelope. The consumer rejects an envelope from any other owner, and that pin is what refuses a second owner.

**Credentials never travel as values.** Tokens stay in their 0600 files. The seed reads each through the shared-input private-file reader: a regular file owned by the user, no group or other access, no symlink. It then checks the token's form. The feed configuration's `tokenFile` names the runtime directory's file, which a reseed keeps and `stop` deletes. The controller credential is stored as the controller stores every credential, by its SHA-256 digest, through `controller_server.register`, which `issue` now uses. A missing or unusable file fails the seed with a fixed line and writes nothing.

**Shared input selected without a preflight read.** `shared-select shared` reads the feed before switching. The seed cannot: its boundary allows no connection, and the orchestrator configures the Hub to accept the wall's feed credential only after the wall's reseed. The seed switches the source in one transaction, and the Poller checks every envelope as the preflight does. A paired run has no legacy tasks to set aside.

**A writer thread, woken, never run in the caller.** In hub-paired, `serve` runs a `PairedWriter` thread. About once per second, or when the map or the controller API wakes it, it runs one pass. The pass ticks the real `shared_source.Poller`, which makes at most one request a second. Then, for every device, it runs the worker's order: prune comets, process the Lines' integration settings queue, apply pending edits, allocate and mark modes applied. The wake only sets an event, so a busy database can never fail an admission. The installed worker's launch never fails one either. The standalone scenarios keep the one-pass stand-in unchanged.

**The controller listener in a thread, on a kept port.** `controller_server.serve` gains an optional `ready` callback, called with the bound port, so the demo can announce the endpoint once it is listening. The core requires every recorded endpoint to come back on its port after any later reseed. So once a run has been paired, a standalone scenario serves the listener again with the controller identity and no accepted credential.

**Exactly one allowed connection shape.** The paired boundary allows only a `socket.connect` of an `AF_INET` stream socket to `('127.0.0.1', <paired port>)` and records it as `allowed`. The port never belongs to an installed service; the seed refuses one, and the boundary ignores one. Datagrams, other ports, other hosts, processes, ctypes and light requests stay refused. `serve` and `drive` take the port from the seed's `demo-run.json`; `seed` allows nothing.

**Checks that survive the orchestrator's order.** The core runs every boundary check after a reseed, and a failed check stops the run. The orchestrator reseeds the wall before the Hub accepts its feed credential. So `paired-feed` reports `skipped` until the wall has accepted its first snapshot since the seed. After that, it fails when the feed is not current or the wall's revision stays behind the Hub's for about 3 s. `device-boundary` in hub-paired fails on any entry other than an allowed connection to the paired port.

**A scripted read for the orchestrator.** `GET /verify/state` is served only by verification runs, through a subclass of the wall server's handler. It is read-only, needs no credential and keeps the map's exact-Host check. It reports the local shared-input inspection and counts of the Lines' integration requests. It never reports a token or token path.

**An independent oracle in the step.** `hub-lifecycle-painted` reads the Hub's feed with the wall's credential and derives each task's key, status, title and evidence from docs/shared-input.md, not from the wall's code. It then compares the page's listed statuses, titles, evidence and painted Line colors.

**A test backstop.** Tests serve, seed and drive through `tests/fixtures/backstop_demo.py`. It adds a second audit hook after the demo's boundary. That hook sees only what the boundary let through and refuses everything but the paired port, and never an installed port. It records any hit, so a boundary regression cannot reach an installed service even in a red test.

## Risks / Trade-offs

- The boundary log grows by about one allowed line a second while paired. The core's lease bounds a run.
- A reseed to `hub-paired` before the credential files exist fails the seed, and the core then stops the run. The orchestrator writes the files first. `restart` of a paired run starts a new runtime directory without them, so pair a new run instead. Restarting one consumer while paired is deferred.
- The browser CI job now installs the controller dependencies, because the paired run serves the controller API and validates snapshots.
- The Hub's controller v1 commands (mode, power, brightness, scene) are admitted and journaled but never executed, because the stand-in never runs the device writer. After 30 s the listener fails such unsent work as `transport-failure` and holds the device, as the controller API guide describes. Its integration settings commands are applied.

## Failure and recovery

A Hub that rejects the feed credential or does not answer leaves the wall serving: shared input reads `unavailable` before the first snapshot and `stale` after one. Tasks stay steady with uncertain evidence, and the Poller retries each second. The first accepted snapshot after a failure resynchronizes without replaying waves or comets, as the consumer already does. A controller port already in use fails the start with `wall-start-failed: controller port already in use`.

## Migration Plan

Source delivery changes no installation. A 1.0 run's standalone behavior is unchanged; runs now record `inputs` and, once paired, `owned.endpoints`.
