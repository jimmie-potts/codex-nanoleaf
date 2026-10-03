## Why

[Nanoleaf #207](https://github.com/jimmie-potts/codex-nanoleaf/issues/207) adds useful controller and worker diagnostics to the accepted shared observability contract. Detached worker output is currently discarded, making failures hard to correlate with machine requests.

## What Changes

- Vendor the accepted immutable observability 1.1.0 package and optional Python host dependencies.
- Explicitly enable bounded host diagnostics for the controller and worker, with Collector export for detached workers.
- Record request handling, admission outcomes and major worker execution/restoration with the shared vocabulary. Preserve authenticated propagation and honest ticket linkage across persisted work.
- Add focused fake-backed checks and usage documentation. Existing device ownership, state, output and visible UI remain unchanged.

## Capabilities

### New Capabilities

- `host-observability`: Optional shared controller and worker diagnostics.

### Modified Capabilities

None.

## Impact

Python host entry points, a verified optional adapter, vendored artifact, dependency pins, tests and existing CI. No installed runtime or physical-device changes. Numerical performance qualification and exhaustive browser, hook and helper coverage remain deferred under the accepted parent scope.
