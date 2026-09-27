## Why

Independent review of [issue #193](https://github.com/jimmie-potts/codex-nanoleaf/issues/193)'s delivery ([PR #195](https://github.com/jimmie-potts/codex-nanoleaf/pull/195), round 1) approved the change with eight P3 findings. Three things were missing. `serve` and `drive` accepted any state directory, including the installation's own. The boundary missed process, foreign-code and interpreter paths that raise no socket or process audit event. And some boundary assertions could fail spuriously, could not fail, or were not attached to failed captures.

## What Changes

- `seed` marks its directory with `demo-run.json`. `serve` and `drive` refuse an unmarked directory, and every command refuses the installation's state directory.
- The boundary also refuses ctypes loads and calls, subinterpreter creation, and the unaudited launcher used by multiprocessing's spawn and forkserver.
- `serve` starts the map's bounded layout retries as the installed map does. `device-read-refused` accepts those retries, and nothing else, during its step.
- The `layout-unavailable` boundary check accepts only the map's layout read. A new negative control, backed by a defect transition whose stand-in contacts the devices, must fail at "no device attempt was recorded during the step".
- Every capture, including a failed one, attaches its boundary record.
- A restart of an expired run is checked to name its predecessor and to leave the frozen proof unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `wall-verification-runs`: every requirement gains the corrections above.

## Impact

`scripts/demo.py`, `scripts/verify/`, the Python and Node tests, the module-dependency guard and the development guide change, in the same PR as #193.

No design document: the corrections follow the existing design's decisions on the boundary, fresh steps and the shared core.
