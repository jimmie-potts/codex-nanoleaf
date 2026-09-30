## Why

The final reviews of [PR #195](https://github.com/jimmie-potts/codex-nanoleaf/pull/195) left two P3 follow-ups, gathered in [issue #196](https://github.com/jimmie-potts/codex-nanoleaf/issues/196). The refused-read step and the `layout-unavailable` boundary check require consecutive layout reads to be recorded at least 9.9 s apart. The map decides its reads 10 s apart, and measured gaps were 10003 to 10010 ms, which leaves about 100 ms of slack. A read recorded more than 100 ms late, for example after a pause or slow I/O, makes a correct map fail `device-read-refused` and `doctor` report `device-boundary: failed`. The module-dependency guard's rebinding check also missed some ordinary Python spellings; that guard is a test and has no specification text.

## What Changes

- The refused-read step and the `layout-unavailable` boundary check accept consecutive layout reads recorded at least 9 s apart, instead of 9.9 s. A read recorded 500 ms late passes. A map that reads on every 1 s poll still fails the spacing, and one without the three-read limit still fails the count.
- The rebinding guard in `tests/test_module_dependencies.py` resolves each assigned or deleted attribute to its root, follows local aliases, and rejects any use of `setattr` or `delattr` other than a direct call. This is a test-only change with no requirement delta.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `wall-verification-runs`: Assertion-backed capture steps; Labelled components and boundary check.

## Impact

`scripts/verify/steps.mjs`, `tests/verify_checks.mjs`, `tests/test_module_dependencies.py` and the development guide. The map, the boundary, the three-read bound and the endpoint rule are unchanged. No installed service or device is affected.

No design document: the change widens one tolerance and extends a test's static check, with no new component, interface or state.
