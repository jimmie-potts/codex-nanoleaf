## Context

See proposal.md for motivation. Frame colors come from module constants in `bridge/bridge.py`: `BASELINE` feeds unused Lines, idle and read Lines, Project-layout status halves, empty Shared Lines and the no-scene fallback, and `COLORS` feeds pulses, waves and Quiet. The comet tail blends from white toward `BASELINE`. `PRIORITY` ranks statuses for overlapping effects. The worker re-sends a looping effect only when its display cache key in `display_v3` changes. Project colors are already stored in SQLite and edited through `/api/project`. The wall map draws with `--wall-*` CSS tokens and lifted `--chip-*` text tokens.

## Goals / Non-Goals

**Goals:**
- One palette, stored once, that the worker and the map both read.
- A color change reaches the lights through the existing dirty flag and display cache, never through task state.
- Upgrades and rollbacks need no migration step.

**Non-Goals:**
- Palette editing from the CLI, controller API, MCP or the integration settings API.
- Per-device or per-project status palettes, presets and animation styles.

## Decisions

### Store only changed roles

A new `palette (role TEXT PRIMARY KEY, color TEXT NOT NULL)` table is created with the other wall tables in `project_map.init`. A missing row means the role uses its default, so an existing installation starts with the new defaults without a data migration. Reset deletes every row. The table has no device column because one palette covers every device. Reading ignores rows with an unknown role or a malformed color, so a damaged row falls back to that role's default instead of stopping the worker. Older code ignores the table, so rolling back keeps working with the old fixed colors.

Alternative considered: a JSON value in `meta`. Rows keep each role independently valid and make partial updates trivial.

### Defaults live in one place

`project_map.DEFAULT_PALETTE` holds the hex defaults. `bridge.py` derives `BASELINE` and `COLORS` from it, so existing callers and tests keep working, and `COLORS` still names the statuses that carry activity. `PRIORITY` is unchanged and still keyed by status.

### The worker reads the palette with its render inputs

`project_map.render_config` sets `config['_palette']` inside the same transaction that reads `event_revision`. A palette write marks the state dirty, which bumps that revision, so a worker that rendered an older palette always sees the change and takes another pass. The preview pass reads the palette too, so `setup --demo` previews the chosen colors. `pixel_color`, `comet_color` and `zone_color` take their colors from `_palette`, falling back to the defaults when it is absent.

`update_display` adds the palette to the display cache key. A changed palette therefore re-sends the current looping effect, computed from the stored pulse epochs, and a pass with an unchanged palette sends nothing new. Task epochs, comets, wave cutoffs, slots and reservations are not touched by a palette write.

### The no-scene fallback keeps today's blue

The `SceneRestorer` fallback draw, used only before any scene is remembered or after it was deleted, renders with a fixed `#193CFF` base. Every other empty-Line color uses the palette base.

### The existing settings write carries the palette

`/api/settings` accepts `palette` as either an object of one to five `role: "#rrggbb"` entries or the string `"default"` for Reset colors. Validation checks every key and value before any write, so an invalid color or an unknown role rejects the whole request. The palette is applied at once, even while a comet plays, because it moves no comet source. The integration settings API validates its own command shape before reaching this shared operation and never forwards `palette`.

### The map derives its colors from `/api/state`

`/api/state` returns the effective palette as lowercase hex for all five roles. The map writes them to the `--wall-*` tokens on the root element; the CSS defaults match the stored defaults for the first paint. Status text colors (`--chip-*`) are derived: the role color is mixed toward white until its contrast against the page background reaches 4.5:1, so labels stay readable even for a black or very dark choice. The similar-color warning compares every pair of roles in CIELAB and warns when the CIE76 difference is below 20. It lists the pairs and never blocks saving. The Colors group is built once and updated in place, so polling keeps an open native color picker and keyboard focus.

## Risks / Trade-offs

- [A palette write re-sends the effect] → The re-send is computed from stored epochs, like a project color change today, so pulses keep their phase and nothing replays.
- [LED colors differ from the screen] → The swatches are suggestions; the operator can pick another without a code change. A physical check needs an explicit request.
- [Off base leaves unused Lines dark] → Task Lines still show, and scene restoration depends on indicators, not colors.
- [The ΔE threshold is a heuristic] → It only warns. Identical colors always warn, and the default palette does not.

## Migration Plan

No migration step. The table is created on first connection. Rollback leaves the table unused.

## Open Questions

None.
