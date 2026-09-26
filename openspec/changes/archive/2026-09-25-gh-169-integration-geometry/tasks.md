## 1. Read route

- [x] 1.1 Add the pure geometry view for Lines, Panels and a device without a layout (TDD). Evidence: controller tests with the fake Lines and Panels layouts cover each device's elements and points, the Lines connector graph, the explicit empty result, null points without drawable geometry, an unknown device, unchanged database bytes and no light request.
- [x] 1.2 Serve `GET /controller/integration/v1/geometry`. Evidence: HTTP test for authentication, origin checks, read scope and an unchanged snapshot shape.

## 2. Consumer contract

- [x] 2.1 Add the closed TypeScript geometry validator and shared fixtures. Evidence: `test_python_typescript_consumer_fixtures` validates the fixtures and the route's actual Lines, Panels and empty outputs.

## 3. Documentation and verification

- [x] 3.1 Document the route in `docs/integration-api.md`. Evidence: the text matches the spec and links resolve.
- [x] 3.2 Run `python3 scripts/check.py`, `npm run check:workflow` and `npm run test:workflow`, then record the results in the PR. The hub companion's fixture test runs in agent-device-hub.
- [x] 3.3 Synchronize and archive this change on the delivery branch, then publish the PR.
