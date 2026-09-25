## 1. Shared frame encoder and patterns

- [ ] 1.1 Extract the `display` encoder into `bridge/effects.py` and route `effect_payload` through it. Evidence: existing status, comet and Panels payload tests pass unchanged.
- [ ] 1.2 Add command validation, the five pattern renderers and the frame and byte bounds (TDD). Evidence: `tests/test_effects.py` covers bounds, per-pattern frames on the 15-Line and two-Line fixtures, direction ordering, paired zones, and the cap staying below the live-verified comet.

## 2. Extension command and journal

- [ ] 2.1 Accept `animation.play` in `integration_api` validation and admission with Free, revision and capacity checks (TDD). Evidence: tests for malformed input, Work/Quiet rejection without a consumed ticket, capacity rejection and Free acceptance.
- [ ] 2.2 Retire queued animations on every explicit mode command and journal the worker's single write (TDD). Evidence: tests for mode retirement, `sent` after the Free handoff, ordering with scene controls, a raising send ending `uncertain` without replay, restart recovery, cancel, expiry and revocation.
- [ ] 2.3 Add the read-scoped `GET /controller/integration/v1/animations` route. Evidence: HTTP test for scope, byte-pure reads and an unchanged snapshot shape.
- [ ] 2.4 Extend the TypeScript consumer and shared fixtures. Evidence: `test_python_typescript_consumer_fixtures` passes with new valid and invalid animation cases and animation receipt results.

## 3. MCP tools

- [ ] 3.1 Add `nanoleaf_animations_list` and `nanoleaf_animation_play` with their transport operations (TDD). Evidence: fake-controller tests for listing, Free playback, the Work/Quiet message, invalid fields rejected before dispatch and scope filtering. Real-protocol tests cover discovery and an end-to-end call.

## 4. Documentation and verification

- [ ] 4.1 Update `docs/integration-api.md`, `docs/local-mcp.md` and `docs/controller-api.md`, and add an ADR for extension animations. Evidence: links resolve and the text matches the specs.
- [ ] 4.2 Run `python3 scripts/check.py`, `npm run test:mcp`, `npm run check:workflow` and `npm run test:workflow`, then record the results in the PR. Live Codex animation playback stays with the owner's explicit request.
- [ ] 4.3 Synchronize and archive this change on the delivery branch, then publish the PR.
