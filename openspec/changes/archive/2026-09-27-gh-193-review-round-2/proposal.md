## Why

Review round 2 of [issue #193](https://github.com/jimmie-potts/codex-nanoleaf/issues/193)'s delivery ([PR #195](https://github.com/jimmie-potts/codex-nanoleaf/pull/195)) approved the change with P3 findings. The refused-read step and the boundary check checked only the shape of the map's layout reads, not how many there were or how far apart they came. A failed seed put the command and absolute paths into `failure.detail`. And `seed`'s refusal of the installation directory exited 1 with a traceback.

## What Changes

- The refused-read step and the `layout-unavailable` boundary check accept only `GET` requests for the whole layout of `192.0.2.1`: at most three since the seed, each recorded at least 9.9 s after the previous one.
- A failed seed is named `demo.py seed failed: <cause>` from the same mapping as a failed start.
- `demo.py seed` refuses the installation's state directory with exit status 2, as `serve` and `drive` do.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `wall-verification-runs`: Named synthetic scenarios; Assertion-backed capture steps; Labelled components and boundary check.

## Impact

`scripts/demo.py`, `scripts/verify/`, the tests, the module-dependency guard, a test fixture and the development guide, in the same PR as #193.

No design document: the corrections tighten existing checks to the behavior the design already describes.
