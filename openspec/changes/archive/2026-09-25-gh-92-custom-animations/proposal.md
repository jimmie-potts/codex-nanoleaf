## Why

[Issue #92](https://github.com/jimmie-potts/codex-nanoleaf/issues/92) lets Codex play a described animation, such as a slow blue-green wave, on the Lines through the local MCP server. The controller accepts no animation input today. Hub architecture requires typed-extension work for arbitrary colors and rules out raw protocol commands.

## What Changes

- Add a typed `animation.play` command to the Nanoleaf-owned `nanoleaf.integration/1.0` extension. It takes a pattern from a fixed set (wave, pulse, breathe, sparkle, gradient), 1 to 8 `#rrggbb` colors, a speed, a direction for spatial patterns and a loop flag. Controller v1 and its vendored contract stay unchanged.
- The controller validates the command, the current configured Lines geometry and the encoded effect size before queueing. The command is admitted only while the desired mode is Free. In Work or Quiet it is rejected before any write and consumes no request ticket, like other extension rejections.
- Animation receipts use the extension's existing request ledger with transport outcomes: `queued`, then `sent`, `failed`, `uncertain` or `cancelled`. `physicalOutcome` stays `unknown`. Any explicit mode command retires a queued animation. The worker never replays an attempted animation.
- The worker plays a queued animation as one journaled `PUT /effects` display write from the existing single Lines writer, with no per-frame streaming. A new frame encoder module is shared by the status display and the animation patterns.
- Add `GET /controller/integration/v1/animations`, a read route that lists patterns, speeds, directions and limits with the request identity and revision needed to play. The 1.0 extension snapshot keeps its exact shape so the hub's exact validator still accepts it.
- Bound effects to the envelope already proven on the device: at most 20 frames per zone and an 8,192-byte request body. The middle-Line comet preview, 9,009 bytes, passed the live comet checks. No live probing is part of this change.
- The local MCP host adds `nanoleaf_animations_list` (read) and `nanoleaf_animation_play` (control). The play tool never switches mode. Its Work/Quiet rejection tells the caller to switch to Free with `nanoleaf_mode_set` first.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `integration-settings-api`: the extension gains one Free-only light command with transport receipts and a separate read route. The requirement that the extension carries no general lighting operations is narrowed to name this exception.
- `device-worker`: the Lines instance plays queued extension animations as journaled one-shot writes.
- `local-mcp-bindings`: the tool surface adds animation discovery and Free-only playback.

## Impact

`bridge/effects.py` (new encoder and patterns), `bridge/bridge.py` (status encoder reuse, worker playback), `bridge/integration_api.py` (validation, admission, journal, read route), `bridge/controller_state.py` (mode commands retire queued animations), `bridge/controller_server.py` (route), `contracts/integration-v1/` (TypeScript consumer and shared fixtures), `mcp/src/` (two tools, transport operations), tests, and `docs/integration-api.md`, `docs/local-mcp.md`, `docs/controller-api.md` and a new ADR. No database migration: the existing `integration_requests` table stores the new rows. Source delivery does not install, register the MCP server with Codex or touch lights. Live acceptance stays with the owner's explicit request.
