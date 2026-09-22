# 0009. Device-aware state for one Linux installation

Status: Accepted for source implementation in [#41](https://github.com/jimmie-potts/codex-nanoleaf/issues/41).

## Context

The bridge stores every placement, reservation, pending edit, comet, mode and
saved scene as if the installation owned one Nanoleaf controller, and the
layout file is a Lines-only zone pairing. The operator wants NL22 Light Panels
beside the Lines on the single Linux installation from ADR 0007. #42 will
schedule a second renderer and #43 will read NL22 geometry; both need a stable
storage and geometry shape first. The protected controller from #28 already
names the Lines device `wall`.

## Decision

Register devices in the private `config.json` under `devices`: id, kind
(`lines` or `panels`), address and a token reference naming the configuration
key that holds the credential. A configuration without that section describes
the original Lines device. That device keeps id `wall`, the identity #28
established for the controller and MCP configuration; the issue's "default
`lines`" is read as "default to the original Lines device", because a second
name for the same controller would split its identity. Changing an address
edits the entry and leaves the id and its state alone.

Key device-scoped state by device with `wall` as the default: slot
assignments, comets, Line preferences, display cache, map settings, pending map
edits, Locate, mode metadata and the saved scene file. Uniqueness is device
plus slot and device plus element, so one task can hold one placement per
device and equal panel IDs on two devices cannot collide. Tool waits stay with
shared task ingestion; the per-device "waiting for a Line" state is derived
from device-scoped slots. Tables whose key must include the device are rebuilt
in place inside the existing initialization transaction, copying rows with the
default; singleton tables gain a column and a unique index. The upgrade is
guarded by inspecting the table's columns, so repeated initialization is a
no-op. Mode metadata keeps its existing keys for the original device and uses
`key@device` for others; only the original device notifies the configured
controller. The saved scene file is `scene-state.json` for the original device
and `scene-state.<device>.json` otherwise.

The layout file becomes version 2 with one entry per device. Each element has
a physical id, its existing number and a zone list: two zones for a Line, one
for a triangle. Legacy Lines-only files still load as the original device and
are not rewritten on read; the installer and position discovery write the new
shape after validation, and a malformed layout is rejected without replacing
the last valid file. Callers that name no device address the original Lines
device.

## Consequences

Existing Linux state upgrades on the next initialization by any hook, CLI, map
or controller process. A committed pre-change fixture proves that tasks,
epochs, preferences, the active comet, pending edits, mode metadata, the saved
scene and protected-API credentials and history survive and that a second run
changes nothing. Older source ignores the added column and would need the
backed-up `layout.json` only if a rewritten file were reverted.

This delivery deliberately omits legacy Windows support, compatibility
adapters and a pool identity separate from device identity (#47). The same
code path would upgrade a Windows database if this source were installed
there, but that path is neither exercised nor qualified. The existing worker
still renders only the original device; #42 owns multi-device scheduling,
targeted commands and the protected API's second device, and #43 owns NL22
geometry and payloads. Installation and physical acceptance remain with #46.
