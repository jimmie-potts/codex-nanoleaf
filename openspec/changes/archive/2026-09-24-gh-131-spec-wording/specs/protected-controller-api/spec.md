## MODIFIED Requirements

### Requirement: General controls execute through the single worker queue

`power.set`, `brightness.set` and `scene.activate` SHALL be admitted through the same request identity, configuration revision, generation, replay and capacity rules as mode commands, and SHALL execute as one journaled transport write by the installation's single worker. A failed or uncertain write SHALL hold that installation exactly as an uncertain mode write does, and neither the worker's automatic retry nor a read SHALL execute the request again; a fresh native request or explicit mode choice authorizes another attempt. An explicit mode command SHALL cancel queued general controls as stale generation before another side effect. This requirement maps to issue #64 AC2 and AC4.

#### Scenario: Identical power requests replay

- **WHEN** a client submits the same `power.set` body twice under one request identity
- **THEN** the second submission joins the pending work or returns the retained receipt, and the device receives at most one write for that request

#### Scenario: Uncertain brightness write is held

- **WHEN** the transport fails after a brightness write may have reached the device
- **THEN** the receipt reports uncertainty with possible prior effects, the worker's automatic retry does not send it again, and a later explicit mode choice can send new work

#### Scenario: Mode command supersedes a queued control

- **WHEN** a browser, CLI or native mode command commits while a general control is queued
- **THEN** the queued control is cancelled with stale generation and is never sent
