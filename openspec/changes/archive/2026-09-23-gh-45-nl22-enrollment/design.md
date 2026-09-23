## Context

See proposal.md for the motivation. After #41 and #43:

- `config.json` may hold a `devices` registry of `{kind, ip, token_ref}` entries. `devices.registry` implies `wall` when the registry omits it. Each credential lives at the configuration key named by `token_ref`.
- `layout.json` holds one entry per device. `devices.save_device_layout` merges one entry under `layout-lock.sqlite`.
- Mode, applied revision, error, preview and the rendering flag are `meta` keys named by `devices.meta_key` (`mode@panels`, for example). Slots, comets, Line preferences, map settings, pending edits, Locate and the display cache are rows with a `device` column. Each device has its own scene file and worker lock file.
- A device without a `mode` key defaults to Work. A worker in Free with no pending mode change sends nothing and does not poll the device.
- Hooks, `launch_worker`, the map's worker launches and shared-input comet targets all call `registered_devices` each time they run. The map, controller and MCP load only `wall`.

The Linux installer (`install_linux.py`) is not copied into the runtime. Its token reader must therefore move to a module the runtime has.

## Goals / Non-Goals

**Goals:**

- One command to add NL22 Panels safely, and one to take them away, both usable from the installed `nanoleaf` launcher and from a source checkout with `--state-dir`.
- Enrollment and removal never disturb `wall`, shared tasks, hooks, listener settings or machine credentials.

**Non-Goals:**

- Enrolling a second Lines device or other Nanoleaf models.
- Changing a registered device's address in place.
- Backup, rollback, service management, or restarting units.
- Windows installations.
- Browser controls (#44).

## Decisions

### Command surface

- `bridge.py device-enroll --ip <address> [--device <id>] [--token-file <path> | --pair]` and `bridge.py device-remove --device <id> [--force]`. `main` hands `device-*` arguments to `enrollment.command`, as it already does for `controller-*` and `shared-*`.
- The id defaults to `panels`. It must match the registry's id pattern and must not be `wall`.
- Both commands refuse to run on Windows and against a state directory under `/mnt/<drive>`. A legacy Windows installation reached from WSL would otherwise have its SQLite written from Linux.
- Rejected alternative: a separate installer-style script like `install_linux.py`. The installed runtime would not have it, and removal needs to be available after installation.

### Credential intake

- Credential sources, in order: `--token-file` (a regular file of at most 1024 bytes, as the installer reads it), `--pair`, or a hidden prompt. The installer's `read_token` moves into `enrollment.py`, and `install_linux.py` imports it from there.
- `--pair` asks the operator to hold the power button until the lights flash, then press Enter. It then sends `POST /api/v1/new` to the device, with no proxy and a short timeout. A refused request (403) explains how to open the pairing window. The returned credential is validated like a typed one and is never printed.
- The credential is stored at key `token@<id>`, and the registry entry's `token_ref` names that key. The `@` form matches `meta_key`, and it cannot collide with Lines' `token` key.

### Verification before any write

- The command reads `GET /api/v1/<token>/` once. It requires `model == "NL22"`, then passes `panelLayout` to `panels.read_layout`, which rejects unsupported shapes, overlap and disconnection. Only after both checks pass does it write anything.
- The command runs the registry checks below before it asks for a credential, so a conflict never costs a pairing or a paste, and repeats them inside the registry lock. It also checks, before writing:
  - the address is a private IPv4 address;
  - the credential is ASCII alphanumeric;
  - no other registered device, including `wall`, uses the address;
  - an existing entry with this id is a Panels entry at the same address, and no other entry uses its credential key (for a new id, `token@<id>`);
  - the saved layout file is valid, since a rerun could not repair a malformed one.
- Rejected alternative: register first and let the worker discover the layout. A wrong model or broken layout would then surface as a worker retry loop instead of a refused command.

### Write order and the Free start

- The whole command runs under an exclusive `registry-lock.sqlite`, so two enrollment or removal commands cannot interleave their read-modify-write of `config.json`.
- New registration (the id is not registered):
  1. Take the id's worker lock without waiting. A running worker means a previous registration is still winding down, so the command refuses.
  2. In two short state transactions, delete any leftover rows and `@<id>` meta keys for the id, then set `mode@<id>` to `free` with no revision keys. Revision and applied revision both read 0, so nothing is pending. Also delete a leftover scene file.
  3. Save the layout entry.
  4. Write `config.json` atomically with the new entry and credential. Every other key and entry is kept as it was, including an implied `wall`.

  The registry write comes last. A failure before it leaves only state for an unregistered id, which no process reads and a later enrollment clears.
- Repeat registration (same id, same address): replace only the credential in `config.json`. Layout, mode, reservations and scene are kept. A running worker picks up the new credential on its next launch or retry, because `load_config` rereads the configuration.
- Activation needs no new code. `mode work --device <id>` bumps that device's revision and sets its wave cutoff to the activation time. No comet was queued for the device while it was in Free. Existing #43 behavior therefore shows only current statuses, with no replayed wave or comet.

### Removal

- `device-remove` requires the device's mode to be Free with the revision applied, so the device has already restored its own scene and receives no further requests. `--force` removes an unreachable device whose Free handoff cannot complete. Its lights then keep whatever they last showed.
- Order:
  1. Write `config.json` without the entry and its credential.
  2. Mark the state dirty so a waiting worker instance wakes.
  3. Wait up to ten seconds for the id's worker lock. A non-`wall` worker checks at the start of each pass, and in the retry loop, that its device is still registered, and returns when it is not.
  4. With the lock held, delete the id's rows, meta keys, layout entry and scene file.
- A failure after the first write (for example a state or file error while stopping the worker or purging) is reported as a partial change with a rerun instruction, never as "nothing was changed". SQLite busy errors are reported without a traceback.
- If the lock is not free in time, the registration is already gone. The command says that state cleanup is pending, and rerunning `device-remove` for the now-unregistered id finishes it. Enrolling the id again also clears it.
- The shared-input backup may still list a removed device's placements. Restoring it re-creates rows for an unregistered id, which no reader uses and a later enrollment clears.

### Service restarts

No unit needs a restart. Hooks, CLI and worker launches read the registry when they run. The wall map, controller and MCP address `wall` only; the map rereads the registry whenever it launches the worker. Enrollment prints this, which satisfies #45 AC5's "tells the operator which units to restart" with an empty set. The optional "restart when asked" branch is not built, because it would restart services for no effect. #44 can revisit this if its device selector caches the registry.

## Risks / Trade-offs

- **A Free worker can stay alive while unread completions exist.** Removal wakes it and the new registration check makes it exit. The bounded wait and the idempotent rerun cover a slow exit.
- **`--force` leaves the last effect on screen.** It exists only for unreachable devices, and the message says so.
- **Unverified pairing on this firmware.** `POST /api/v1/new` follows the published Nanoleaf OpenAPI. The token-file path remains available, and #46 records whether pairing works on the user's NL22 (firmware 5.2.2).
- **Hand-edited registries.** Enrollment preserves unknown configuration keys and entries. It refuses to change an entry it does not own rather than repairing it.

## Migration Plan

Nothing migrates. Source delivery changes no installation. After #46 copies this source into the Linux runtime, the operator runs `nanoleaf device-enroll` and then `nanoleaf mode work --device panels`. To back out, run `nanoleaf mode free --device panels`, wait for status to show it applied, then run `nanoleaf device-remove --device panels`. Enrollment never changes a registered address; if the Panels' address changes, remove and enroll again (their reservations are cleared) or keep the address fixed in the router.
