## Context

See proposal.md. Runtime state lives in one private Linux SQLite database opened through the bridge's initialization transaction, plus `config.json` (address, credential, ports), `layout.json` (Lines pairing and cached geometry) and `scene-state.json`. Every module reads `config['line_groups']`, `slots`, `line_prefs`, singleton `map_settings`/`map_pending`/`locate`/`display_v3` rows and `meta` mode keys as if there were one device. The controller ledger already names the device `wall`.

## Goals / Non-Goals

**Goals:** one registry, one default device, device-keyed state with a lossless in-place migration, a per-device layout shape that legacy files still satisfy, and unchanged behavior for callers that name no device.

**Non-Goals:** rendering or scheduling a second device, NL22 layout discovery, a pool identity, Windows migration, changing the controller API's single configured target, or a compatibility adapter layer.

## Decisions

- Default device id is `wall`, kind `lines`. #28 established `deviceId` `wall` in the controller identity, the MCP configuration and the Linux installer. The issue's "default `lines`" wording is read as "default to the original Lines device"; giving that device a second name would create two identities for one controller. Alternative rejected: a new id `lines` with a mapping to `wall`.
- Registry lives in `config.json` under `devices`, keyed by id, with `kind`, `ip` and `token_ref` (the config key holding the credential). A configuration without `devices` implies `wall` from the top-level `ip` and `token`. Address and credential already live in this private file; the database never stores credentials. Alternative rejected: a `devices` table, which would duplicate the address and need the credential elsewhere.
- Device-scoped tables gain a `device` column with default `wall`. Tables whose key must include the device (`slots`, `comets`, `line_prefs`) are rebuilt in place inside the initialization transaction, copying rows with the default, because SQLite cannot alter a primary key. Singleton tables (`map_settings`, `map_pending`, `locate`, `display_v3`) receive `ALTER TABLE ... ADD COLUMN` plus a unique index on `device`; rows are addressed by device instead of `id = 1`. Both paths are guarded by inspecting the table's columns, so a second run changes nothing. Column order keeps `device` last so positional readers of the shared-input backup keep working.
- Mode metadata stays in `meta`. The default device keeps the existing keys; another device uses `key@device`. This keeps the controller ledger and every existing reader unchanged. Only the default device notifies the single configured controller; a second device's mode change is local until #42 widens the API.
- The saved scene file is `scene-state.json` for the default device and `scene-state.<device>.json` otherwise. Device ids use the controller's neutral id characters, so the file name is safe.
- `layout.json` gains `version: 2` with `devices.<id>` entries holding `kind`, `elements` (`id`, `number`, `zones`, `position`) and the existing `zone_geometry`/`connector_geometry`. A normalizer accepts both shapes and validates zone counts per kind. Legacy files are not rewritten on read; the installer and the existing position discovery write the new shape after validation. The Lines element id remains the sorted zone pair (`a:b`); a triangle's id is its panel ID. Alternative rejected: rewriting legacy files during load, which would change files that tests and the wall map watch.
- Functions take the device from the loaded configuration (`config['device']`) or an explicit `device=` keyword defaulting to `wall`. `load_config(directory, device)` resolves the registry entry, credential and layout entry for that device and still exposes `line_groups`/`line_positions` for the renderer.

## Risks / Trade-offs

- [Rebuilding tables inside the initialization transaction on a live installation] → guarded by column inspection, executed once under `BEGIN IMMEDIATE`, covered by the pre-change fixture test that compares every preserved value and epoch.
- [Positional `INSERT ... VALUES` statements break when a column is added] → all writers name their columns; the suite exercises each table.
- [Legacy readers of `layout.json` outside the bridge] → `integration_api` and the wall map's geometry cache read through the same normalizer; the backup script copies the file unchanged.
- [`DELETE FROM display_v3` and similar global clears] → they only invalidate caches or reset all devices on explicit reset, which is a superset of the previous behavior and safe.
- [Rollback to older source] → older code ignores the extra column and the `version` key of a legacy file, but a rewritten `layout.json` would need restoring from the backup; documented in the ADR.

## Migration Plan

Migration is implicit: the next initialization by any hook, CLI, map or controller process upgrades the schema in one transaction. No installer or service change is needed. The fixture test proves the upgrade and its idempotence with the committed pre-change dump.
