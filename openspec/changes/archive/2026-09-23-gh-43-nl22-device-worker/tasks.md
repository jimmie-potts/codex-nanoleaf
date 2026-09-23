## 1. Device worker

- [x] 1.1 Launch and lock one worker instance per registered device, with a validated `--device` target on `worker`, `mode`, `status` and device-specific `setup` operations. Evidence: focused red-then-green tests show that a launch starts one instance per device, that a second instance for a device exits, that an untargeted command addresses `wall` whatever the registry order, and that an unknown target is rejected without a state change.
- [x] 1.2 Scope the worker's mode, applied revision, error, preview, rendering flag and display cache to its device. Keep shared-feed polling, controller requests, general controls, overrides, the hold, scene discovery and the integration queue on `wall`. Evidence: tests with fake Lines and Panels transports cover mixed modes, per-device scene restoration and a Free handoff that stops requests. They also show a Panels outage that leaves Lines' due update, error and controller outcome unchanged, and machine requests that never reach Panels.
- [x] 1.3 Queue completion comets per Work device, keep read evidence shared, and make `setup --reset`, `--refresh` and shared-source switching state or respect their device scope. Evidence: tests cover a completion with mixed modes, reading that clears both devices, an override during a Panels comet, a later Panels registration without replay, a targeted refresh, and shared-source switching that preserves bound placements on both devices.

## 2. NL22 renderer

- [x] 2.1 Read NL22 layouts into validated one-zone triangle elements with cached coordinates, orientation and neighbors, and discover and save them through `load_config` for a Panels device without a layout. Evidence: red-then-green tests use the synthetic 18-triangle fixture and a smaller valid subset, and show Rhythm exclusion and the rejection of unsupported shapes, duplicates, overlap and disconnection.
- [x] 2.2 Render one zone per triangle without the logical-panel flag and without project halves. Keep the Lines payload unchanged. Evidence: decoded payload tests cover triangle zone counts, frame timing, waves by triangle distance, red/yellow priority under a comet, a six-triangle reservation, idle baseline and one-triangle Locate. The existing Lines payload tests continue to pass.

## 3. Documentation and delivery evidence

- [x] 3.1 Add ADR 0010. Update ADR 0009's gap paragraph, the bridge guide, the Linux guide's writer wording and the OpenSpec context, and inspect the rendered text and links.
- [x] 3.2 Run the full Python suite, browser checks, MCP source checks and workflow checks. Confirm that the protected contract fixtures are unchanged. Synchronize and archive this change before final independent review, and record the results in the PR.
