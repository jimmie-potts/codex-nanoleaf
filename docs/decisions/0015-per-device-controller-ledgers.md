# 0015. Each device owns its own controller ledger

Status: Accepted by the owner on 2026-09-25 for source implementation of [#113](https://github.com/jimmie-potts/codex-nanoleaf/issues/113). It replaces the "Single-owner work" rule of [ADR 0010](0010-per-device-worker-and-nl22.md).

## Context

[ADR 0010](0010-per-device-worker-and-nl22.md) runs one worker instance per registered device, and each instance writes only to its own device. It also gave all protected-controller and integration work to the `wall` instance: the request journal, general controls, overrides, the hold and scene discovery. The controller had one identity and one ledger, so the hub, the dashboard and Codex could reach only the Lines. The NL22 Panels could be controlled only from the CLI.

For the controller to reach the Panels, something must execute Panels commands. If the `wall` instance did it, the Panels would have two writers.

## Terms

This decision uses these terms. [#163](https://github.com/jimmie-potts/codex-nanoleaf/issues/163) owns a project-wide glossary.

- **Worker instance:** `bridge.py worker --device <id>`. It is the only process that sends light requests to its device.
- **Controller:** the protected local HTTP API that the hub, the dashboard and the MCP host call. It never contacts a device. It records a command and wakes the workers.
- **Controller ledger:** the controller's records for one device: identity and epoch, configuration revision, generation, request journal (each admitted command with its receipt), event feed, saved-scene identities, overrides and hold.
- **Hold:** after a failed or uncertain write, that device's automatic retries stop until a fresh command or an explicit mode choice arrives.
- **Shared feed poller:** reads the hub's task feed and projects tasks into the shared database that every device's worker reads.
- **Integration settings queue:** extension edits of shared map configuration, such as project colors and task assignment.

## Decision

- **One ledger per device.** The controller keeps one ledger per configured device. The original Lines ledger keeps its identity, epoch, receipts, cursor, scene IDs and unsuffixed meta keys. Other ledgers use the ADR 0009 `key@device` names for their overrides and hold.
- **Each worker instance owns its own ledger.** It recovers that ledger's attempts, stops on that ledger's hold, and applies that ledger's overrides. It journals and executes that ledger's mode, power, brightness and scene commands, and records that device's saved scenes. It never touches another device's requests. An instance without a ledger behaves as before.
- **The `wall` instance keeps the shared work.** It alone polls the shared feed, applies the integration settings queue and plays requested animations. Every device already reads the tasks and settings those produce.
- **Adding a device.** `controller-configure` with the original controller and source IDs and a registered device ID other than `wall` adds that device's ledger. Redirecting an existing identity is still refused. So is naming an unregistered device, or naming another registered device as the first ledger.
- **Credentials.** One credential authorizes every configured device, because a single operator runs this installation. Issuing, revoking or disabling cancels the affected queued work on every device and holds each affected device.
- **Mode.** A mode change for a device, from the CLI, the map or the controller, advances only that device's ledger and cancels only its queued controls. Power, brightness, mode and `scene.activate` follow the same mode rules on every device.
- **Integration extension.** The extension is read-only for every device except the Lines. Its snapshot keeps the exact key set and shows that device's identity, revision, mode and named scenes. It marks the configuration operations unsupported. Commands, including `animation.play`, fail with `unsupported-capability` before reservation.
- **MCP.** An optional `panelsDeviceId` binds the Panels as a second fixed target. The Panels get status, mode and scene tools, and the animation tools stay Lines-only.
- **Display version 2.0.** The Panels accept `display` version `2.0` custom effects without `logicalPanelsEnabled`. The Panels task display sends exactly that payload. The [#46 acceptance](https://github.com/jimmie-potts/codex-nanoleaf/issues/46) on the installed NL22 (firmware 5.2.2, 2026-09-24) showed Work pulses, outward waves and the completion comet. This answers the open question in ADR 0010 for [#92](https://github.com/jimmie-potts/codex-nanoleaf/issues/92). The meaning of a triangle's orientation remains unconfirmed by the official text.

## Consequences

- **State upgrade.** The controller tables gain a `device` column. The next hook, CLI, map, worker or listener start migrates them in place, and a second run changes nothing. Older source still reads the Lines ledger, but its native admission fails closed with `transport-failure` and writes nothing. Rolling back source therefore suspends native admission until the newer runtime returns.
- **Concurrency.** Two worker instances now execute controller work in the same database. Their rows are partitioned by device, and each pass keeps the existing `BEGIN IMMEDIATE` transactions and the five-second busy timeout from ADR 0010.
- **Unchanged.** A registry without a Panels ledger behaves as before, and so do callers that name no device and the Lines' wire contract and fixtures.
- **Hub gap.** The hub's closed extension validator currently requires every configuration operation to be supported. Until the hub accepts the Panels' read-only snapshot, the hub's extension status for the Panels fails. Hub v1 control and MCP don't depend on it.
- **Out of scope.** Configuring the Panels ledger on the installed runtime, the hub entry and physical checks need the owner's request. Panels animations and a combined device pool ([#47](https://github.com/jimmie-potts/codex-nanoleaf/issues/47)) remain separate.
