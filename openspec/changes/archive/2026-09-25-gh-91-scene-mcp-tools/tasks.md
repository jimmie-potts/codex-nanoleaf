## 1. MCP scene tools

- [x] 1.1 Add a `scenes` transport operation for `GET /controller/integration/v1/snapshot` and bind `nanoleaf_scenes_list` (read scope) that validates the response's `apiVersion`, matching identity and bounded `{id, name?}` entries, exposing nothing else from that snapshot.
- [x] 1.2 Bind `nanoleaf_scene_activate` (control scope) that builds a `scene.activate` request from the caller's `requestId`, `expectedConfigurationRevision`, `expectedGeneration` and `sceneId`, reusing the existing receipt/failure handling used by `nanoleaf_mode_set`.
- [x] 1.3 Update the `local-mcp-bindings` spec and `docs/local-mcp.md` for the two new tools and their scopes.

## 2. Verification

- [x] 2.1 Fake-controller unit tests cover: listing scenes with IDs and names, activation success, a Work/Quiet rejection receipt, an unknown scene ID rejected before dispatch, and revoked/scope-mismatched dispatch never reaching the transport.
- [x] 2.2 Real-protocol fake-controller tests cover discovery of the two new tools, an end-to-end list call, an end-to-end activation, an unknown-scene rejection and read-scope-only discovery filtering out `nanoleaf_scene_activate`.
- [x] 2.3 Run `npm run test:mcp` and `python3 scripts/check.py`; record results in the PR. Live Codex registration and physical scene playback remain separately authorized per the issue.
