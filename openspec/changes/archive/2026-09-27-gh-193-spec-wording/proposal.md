## Why

CI for [PR #195](https://github.com/jimmie-potts/codex-nanoleaf/pull/195) on Python 3.12 showed that the boundary's ctypes claim in [issue #193](https://github.com/jimmie-potts/codex-nanoleaf/issues/193)'s `wall-verification-runs` spec was too broad. Python 3.12 raises no audit event for a call through a ctypes function resolved before the boundary; Python 3.14 does.

## What Changes

- `wall-verification-runs`: the device boundary refuses ctypes library loads and symbol lookups on every supported Python, and foreign calls on Python 3.14. The ctypes scenario says the same.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `wall-verification-runs`: Device boundary.

## Impact

Specification wording, plus the version-precise ctypes attempts in `tests/test_demo_runs.py` and the development guide, in the same PR as #193.

No design document: this narrows a claim to observed behavior.
