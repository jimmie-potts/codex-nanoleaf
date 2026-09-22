## 1. Capabilities, discovery and desired state

- [x] 1.1 Advertise power, brightness and discovered scenes in the ledger snapshot and admission state, with desired power/brightness read from the override keys; verify with red-then-green tests that the snapshot validates against the shared schema, `media`/`zones`/`preview` stay unsupported and the 220 fixture cases still pass.
- [x] 1.2 Record discovered scene names from the worker's observation into the ledger as bounded opaque IDs and expose names through the extension snapshot; verify a worker run advertises the fake device's scenes as IDs only in v1, lists names in the extension, bounds the list at 256 and omits over-long names, and that repeated observation without change writes no event.

## 2. Admission and execution

- [x] 2.1 Admit `power.set`, `brightness.set` and `scene.activate`, record overrides, clear the hold, gate scenes to Free with a retained `unsupported-capability` receipt, and queue a one-shot; verify replay/join, conflict, Work/Quiet scene rejection before any write, unknown scene rejection and desired-state reporting with focused tests.
- [x] 2.2 Execute queued one-shots in the worker with per-request journaling and mode-command cancellation; verify sent receipts with one transport operation, uncertain transport hold without automatic retry, cancellation by a later mode command, epoch preservation and no Free polling after a scene write.

## 3. Override policy in rendering and modes

- [x] 3.1 Apply the brightness override in `render` and `SceneRestorer`, add the `quiet_brightness` marker with legacy defaulting, and gate the sender while desired power is off; verify Work indicators at the override, Quiet idle at the override, power-off suppression with continued tracking, and the scene-state key set and privacy test.
- [x] 3.2 Clear overrides in `change_mode` for every owner, including same-mode commands, which then re-render; verify Work idle and Quiet idle overrides are reapplied by a same-mode command, Free handoff clears them, the tray/CLI path behaves the same and existing mode tests stay green.

## 4. Documentation and delivery evidence

- [x] 4.1 Update `docs/controller-api.md`, `docs/integration-api.md` and `bridge/README.md` with the capability matrix, override policy, scene gate and snapshot semantics; inspect the rendered text and links.
- [x] 4.2 Run the full Python suite, browser, MCP and workflow checks; synchronize and archive this change on the branch before final independent review and record the commands, results and revision in the PR. The linked hub companion PR (fixture pins, compatibility record, work guide) follows the merged revision under the hub maintenance procedure and is tracked in the PR and issue, not here.
