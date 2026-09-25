## 1. Decision and ledger state

- [x] 1.1 Add ADR 0015 and a status note in ADR 0010. Observable: the ADR records per-device ledgers, the scope `wall` keeps, credential scope, read-only extension for other devices, the display v2.0 answer from #46, and the migration and rollback consequences.
- [x] 1.2 Migrate `controller_meta`, `controller_requests` and `controller_events` to per-device keys inside `connect_state`. Observable: a pre-change ledger fixture keeps identity, epoch, receipts, cursor, hold and scenes, replays a retained request, and a second run changes nothing.
- [x] 1.3 Make every `controller_state` operation device-scoped with `wall` as default and add `controller-configure` for a registered device. Observable: configure tests cover add, repeat, unregistered and redirect.

## 2. Controller routes and worker ownership

- [x] 2.1 Route snapshot, feed, devices and commands by `deviceId`, with credentials covering every ledger. Observable: HTTP tests read both devices and admit a Panels command with its own sequence.
- [x] 2.2 Notify the target device's ledger on every mode change. Observable: a Panels mode change advances only the Panels generation and cancels only Panels controls.
- [x] 2.3 Give each worker instance its own ledger's recovery, hold, overrides, journaled execution and scene discovery. Observable: side-by-side fake-device tests show commands only on their own transport, a Panels hold leaving the Lines running, and per-device scenes.
- [x] 2.4 Serve a read-only extension view for other devices. Observable: extension tests cover the Panels snapshot, rejected commands, receipt, cancel and animations routes.

## 3. MCP

- [x] 3.1 Add optional `panelsDeviceId` and the four `nanoleaf_panels_*` tools. Observable: MCP tests cover discovery with and without the field, a Panels mode request naming the Panels, and a rejected device argument.

## 4. Documentation and verification

- [x] 4.1 Update `docs/controller-api.md`, `docs/local-mcp.md`, `docs/integration-api.md`, `docs/linux-install.md`, `bridge/README.md` and the enrollment guidance. Observable: each page describes configuring the Panels ledger and the per-device behavior.
- [x] 4.2 Run `python3 scripts/check.py`, `npm run test:mcp` and `npm run check:workflow`, and record the results in the PR. The live hub entry and physical checks stay with the owner.
- [x] 4.3 Synchronize and archive this change on the delivery branch and verify each affected main spec.
- [x] 4.4 Publish the PR with the owner walkthrough. Observable: the PR records the walkthrough, local results, independent Standards and Specification reviews and CI for its head.
