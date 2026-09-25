## MODIFIED Requirements

### Requirement: General controls execute through the single worker queue

`power.set`, `brightness.set` and `scene.activate` SHALL be admitted through the same request identity, configuration revision, generation, replay and capacity rules as mode commands, and SHALL execute as one journaled transport write by the target device's single worker. A failed or uncertain write SHALL hold that device exactly as an uncertain mode write does, and neither the worker's automatic retry nor a read SHALL execute the request again; a fresh native request or explicit mode choice authorizes another attempt. An explicit mode command SHALL cancel that device's queued general controls as stale generation before another side effect. This requirement maps to issue #64 AC2 and AC4 and to [issue #113](https://github.com/jimmie-potts/codex-nanoleaf/issues/113) scope 3.

#### Scenario: Identical power requests replay

- **WHEN** a client submits the same `power.set` body twice under one request identity
- **THEN** the second submission joins the pending work or returns the retained receipt, and the device receives at most one write for that request

#### Scenario: Uncertain brightness write is held

- **WHEN** the transport fails after a brightness write may have reached the device
- **THEN** the receipt reports uncertainty with possible prior effects, the worker's automatic retry does not send it again, and a later explicit mode choice can send new work

#### Scenario: Mode command supersedes a queued control

- **WHEN** a browser, CLI or native mode command commits while a general control is queued
- **THEN** the queued control is cancelled with stale generation and is never sent


## ADDED Requirements

### Requirement: Per-device controller ledgers

The controller SHALL keep one ledger per configured device, with its own identity and epoch, configuration revision, generation, request journal and sequence, event feed, saved-scene identities, overrides and hold. The original ledger SHALL keep its identity, epoch, retained receipts, cursor and scene IDs in storage that older source can still read and write. Removing a device SHALL delete its ledger. `controller-configure` SHALL add a ledger only for a registered device other than the original one, with the original controller and source IDs, and SHALL still reject redirecting an existing identity. `/controller/v1/devices` SHALL list every configured device's snapshot, the original first. Snapshot, feed and command routes SHALL select the ledger named by `deviceId`, and one credential SHALL authorize every configured device. Power, brightness, mode and `scene.activate` SHALL follow the same mode rules on every device. This requirement maps to [issue #113](https://github.com/jimmie-potts/codex-nanoleaf/issues/113) scope 1 and 3 and AC1.

#### Scenario: Both devices are listed

- **WHEN** Lines and Panels ledgers are configured and an authorized client reads `/controller/v1/devices`
- **THEN** it receives two snapshots, Lines first, each with its own device identity, epoch, revision, generation and scene IDs

#### Scenario: Adding a registered device

- **WHEN** the operator configures the registered Panels with the original controller and source IDs
- **THEN** a Panels ledger with a new epoch is created, repeating the command changes nothing, the original ledger is unchanged, and configuring an unregistered device or a different controller ID is rejected

#### Scenario: Scene activation on the Panels in Work

- **WHEN** a client activates an advertised Panels scene while the Panels are in Work and the Lines are in Free
- **THEN** the request fails with `unsupported-capability` and a retained receipt, and neither device receives a write

#### Scenario: Existing ledger stays compatible with older source

- **WHEN** an installation with a pre-change single ledger, retained receipts and a hold is opened and a Panels ledger is added
- **THEN** the original tables' schema and rows are unchanged and still accept the older source's writes, the hold survives, and a retained request replays its original receipt

#### Scenario: Removing the Panels

- **WHEN** the operator removes the Panels after they were added to the controller
- **THEN** their ledger is deleted, `/controller/v1/devices` lists only the Lines, and a later Panels request is forbidden
