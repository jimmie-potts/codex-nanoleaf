## Why

[Issue #194](https://github.com/jimmie-potts/codex-nanoleaf/issues/194) lets [Hub #495](https://github.com/jimmie-potts/agent-device-hub/issues/495)'s integrated preview pair one disposable wall run with one disposable Hub run. The wall must then act as a real Hub consumer: it serves the controller API the Hub calls and follows the Hub's session feed. Today's wall run ([#193](https://github.com/jimmie-potts/codex-nanoleaf/issues/193)) serves only the map page, and its boundary refuses every connection, loopback included.

## What Changes

- A `hub-paired` scenario. Its seed reads two credential files from the run directory, which Hub #495's orchestrator writes. It registers the Hub's controller credential by its digest and configures shared input to follow the paired Hub run's feed. The Hub origin is the non-secret run input `hub-feed` of app-verify 1.1, required by this scenario only.
- `demo.py serve --controller-port` also serves the real controller API listener in a thread, announced as the ready line's `controller` endpoint. From the hub-paired reseed on, every later scenario serves it again on the same port, as the core requires. A standalone scenario accepts no Hub credential there.
- In hub-paired, the worker stand-in is a thread that runs the real shared-input Poller and the integration settings queue about once per second. It never renders or sends.
- The boundary of a hub-paired process also allows TCP connections to `127.0.0.1` on the paired Hub's port, never an installed service's port, and records each as `allowed`. Every light request and every other target stays refused.
- The `device-boundary` check accepts, in hub-paired, only allowed connections to the paired port. A new `paired-feed` check requires the feed to be current at the Hub's revision. It is `skipped` for other scenarios and until the first snapshot arrives.
- A read-only `GET /verify/state` route on the run's map reports feed freshness and the integration settings the stand-in applied, for the orchestrator's assertions.
- A `hub-lifecycle-painted` capture step, and two negative controls: the paired stand-in polls the installed Hub's port, or sends the effect to each device.
- `@jimmie-potts/app-verify` moves to 1.1.0. `controller_server.register` accepts a caller-supplied credential, which `issue` now uses, and `controller_server.serve` takes an optional `ready` callback.

The standalone scenarios, their transitions, steps, controls and boundary proof are unchanged. Their receipts gain a `paired-feed` check reported as `skipped`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `wall-verification-runs`: Named synthetic scenarios; Served run on its own port and state; Device boundary; Driven task transitions; Assertion-backed capture steps; Negative controls fail; Labelled components and boundary check; Supervised runs through the shared core; and a new Hub-paired runs requirement.

## Impact

`scripts/demo.py`, `scripts/verify/`, `bridge/controller_server.py` (credential registration and the `ready` callback, with CLI behavior unchanged), the Python and Node tests, two test fixtures, the vendored core archive, `package.json` and its lockfile, the browser CI job (it installs the controller dependencies the paired run needs) and the development guide. No installation, runtime state, service, port or device changes. Nanoleaf mode, power and brightness execution, comets, acknowledgment and restarting one consumer while paired stay deferred, as the issue lists.
