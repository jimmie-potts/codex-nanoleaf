## MODIFIED Requirements

### Requirement: Supported modes preserve existing ownership

The controller SHALL advertise Work, Quiet and Free as supported modes, power as supported, brightness as supported with the typed 0 to 100 bound, and scenes as supported with the discovered saved-scene identities bounded to 256 IDs; media, zones and preview SHALL remain unsupported. Accepted mode requests SHALL use the installation's existing state coordination and single light worker on its owning operating system. Existing mode brightness, scene restoration, pulse timing, unread behavior, project reservations SHALL remain intact; legacy Windows installations SHALL retain their WSL forwarding boundary. This requirement maps to issue #28's worker-ownership and unavailable-preview criteria and to [issue #64](https://github.com/jimmie-potts/codex-nanoleaf/issues/64) AC1; the retained baseline is the [bridge guide](../../../bridge/README.md).

#### Scenario: A client requests Quiet

- **WHEN** an authorized fresh command requests Quiet
- **THEN** the existing worker applies the current Quiet policy and the API does not independently send a light request

#### Scenario: A client requests unsupported brightness or preview

- **WHEN** a client inspects capabilities, requests a brightness outside 0 to 100, or requests a media, zone or preview operation
- **THEN** power, brightness and scenes are declared supported with their typed constraints, the out-of-range brightness fails validation, media, zones and preview are explicitly unavailable, and the unsupported operation is rejected through the shared contract without a new effect

#### Scenario: Installed WSL command dispatch

- **WHEN** a WSL controller command targets the legacy Windows installation
- **THEN** it forwards to Windows before opening controller state, or fails without state changes when Windows is unavailable

#### Scenario: Linux-owned controller command

- **WHEN** a controller command targets the fresh Linux installation
- **THEN** it uses only that installation's Linux state and worker without Windows forwarding

## ADDED Requirements

### Requirement: General controls execute through the single worker queue

`power.set`, `brightness.set` and `scene.activate` SHALL be admitted through the same request identity, configuration revision, generation, replay and capacity rules as mode commands, and SHALL execute as one journaled transport write by the installation's single worker. A failed or uncertain write SHALL hold that installation exactly as an uncertain mode write does, and neither the worker's automatic retry nor a read SHALL execute the request again; a fresh native request or explicit mode choice authorizes another attempt. An explicit mode command SHALL cancel queued general controls as stale generation before another side effect. This requirement maps to issue #64 AC2 and AC4.

#### Scenario: Identical power requests replay

- **WHEN** a client submits the same `power.set` body twice under one request identity
- **THEN** the second submission joins the pending work or returns the retained receipt, and the device receives at most one write for that request

#### Scenario: Uncertain brightness write is held

- **WHEN** the transport fails after a brightness write may have reached the device
- **THEN** the receipt reports uncertainty with possible prior effects, the worker's automatic retry does not send it again, and a later explicit mode choice can send new work

#### Scenario: Mode command supersedes a queued control

- **WHEN** a browser, tray, CLI or native mode command commits while a general control is queued
- **THEN** the queued control is cancelled with stale generation and is never sent

### Requirement: Brightness and power overrides persist until the next explicit mode command

A `brightness.set` command SHALL be accepted in Work, Quiet and Free and SHALL record a user override that the worker applies to every brightness it writes in the current mode: Work task indicators and comets, Quiet steady colors, the blue fallback, and the remembered scene when it is restored while idle. A `power.set` command SHALL be accepted in all three modes as one write; while desired power is off the worker SHALL send no indicator, restoration or preview writes, and task tracking SHALL continue. The next explicit mode command from any owner, including the same mode, SHALL clear both overrides and reapply that mode's policy: Work indicators at 30% and the remembered scene at its remembered brightness, Quiet at 10%, Free's one-time handoff, and lights on. Overrides SHALL NOT change the remembered scene brightness. This requirement maps to issue #64 AC3.

#### Scenario: Work indicators use the override

- **WHEN** brightness 60 is accepted while Work indicators are showing
- **THEN** the device receives brightness 60 at once and later indicator writes in Work use 60 instead of 30

#### Scenario: Quiet idle keeps the override and same-mode Quiet reapplies 10%

- **WHEN** brightness 50 is accepted while Quiet shows the remembered scene, and an explicit Quiet command follows
- **THEN** the scene plays at 50 until that command, after which the worker writes 10% and the remembered brightness is unchanged

#### Scenario: Work idle override is reapplied by a same-mode Work command

- **WHEN** brightness 70 is accepted while Work shows the remembered scene, and an explicit Work command follows
- **THEN** the scene plays at 70 until that command, after which the worker restores the remembered brightness without re-selecting the scene

#### Scenario: Power off suppresses indicator writes until a mode command

- **WHEN** power off is accepted in Work and a task status then changes
- **THEN** the device receives one power-off write and no indicator writes, task placements and epochs continue, and the next explicit mode command renders the current indicators with lights on

#### Scenario: Free handoff clears an override

- **WHEN** a brightness override is active in Work and the user chooses Free
- **THEN** the override is cleared, Free performs its existing one-time handoff, and no later Free polling occurs

### Requirement: Saved scenes are discovered and activated only in Free

The worker's existing scene observation SHALL record the device's saved scene identities, bounded to 256, as opaque neutral IDs that reveal no scene name in the shared snapshot. `scene.activate` SHALL be accepted only when the desired mode is Free; in Work or Quiet it SHALL return the typed `unsupported-capability` failure before any device write, with a replayable receipt and no new wire value. In Free it SHALL perform one selection write through the worker, start no polling, and preserve task pulse epochs, comet sources, unread tracking and reservations. This requirement maps to issue #64 AC4.

#### Scenario: Scene requested in Work

- **WHEN** a client requests a discovered scene while the desired mode is Work or Quiet
- **THEN** the request fails with `unsupported-capability`, the failure receipt is retained for replay, and the device receives no write

#### Scenario: Scene activated in Free

- **WHEN** a client requests a discovered scene while the desired mode is Free
- **THEN** the worker sends exactly one selection write, the receipt reports transmission, and the worker performs no further controller polling in Free

#### Scenario: Unknown scene identity

- **WHEN** a client requests a scene ID that discovery has not advertised
- **THEN** the request fails with `unsupported-capability` and nothing is written

### Requirement: Desired general-control state stays separate from observation

Snapshots SHALL report desired power and brightness as known only while an override is active and as unknown otherwise, alongside the desired mode; pending general controls SHALL appear in the bounded pending list; last successful send, last outcome and observation SHALL remain separate, and observation SHALL stay unknown unless the worker holds evidence. This requirement maps to issue #64 AC5.

#### Scenario: Snapshot after an accepted brightness command

- **WHEN** a client reads the snapshot after `brightness.set` is accepted and before the worker sends it
- **THEN** desired brightness is known, the command is pending, last successful send is unchanged and observation remains unknown

#### Scenario: Snapshot after a mode command

- **WHEN** a client reads the snapshot after an explicit mode command clears the overrides
- **THEN** desired power and brightness are unknown again and the desired mode reflects the command
