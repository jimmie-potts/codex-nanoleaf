## Why

[Issue #193](https://github.com/jimmie-potts/codex-nanoleaf/issues/193) needs an agent to start the real wall with synthetic Lines and Panels state, exercise presentation, configuration and animation states, keep assertion-backed proof and hand over a disposable preview, without communicating with physical lights. The owner chose one shared lifecycle core in the Hub ([Hub #494](https://github.com/jimmie-potts/agent-device-hub/issues/494)) that implements the [app verification contract](https://github.com/jimmie-potts/agent-device-hub/blob/main/docs/app-verification.md); this repository supplies only the wall plug-in and its wrapper command.

## What Changes

- `scripts/demo.py` gains `scenarios`, `seed`, `serve` and `drive` commands. `serve` starts the wall server the way the installed map starts, over a caller-owned state directory on `127.0.0.1` and a requested or kernel-chosen port. The existing no-argument demo keeps its temporary reference state.
- Every demo entry point installs a process boundary that refuses and records outbound sockets, datagram sends, new processes and light requests. A refusal looks like an unreachable device to the wall server.
- Named scenarios (`reference`, `empty`, `layout-unavailable`) and named task transitions, applied through the actual hook handler, including known-wrong defect transitions.
- A wall plug-in (`scripts/verify/`) with readiness, components, a start-time boundary check and capture steps whose assertions read painted and listed observations, with negative controls that must fail.
- Pending the core release: the `npm run verify --` wrapper and the vendored core archive.

## Capabilities

### New Capabilities

- `wall-verification-runs`: synthetic scenarios, the served run, the device boundary, driven transitions and the assertion-backed capture steps of the wall plug-in.

### Modified Capabilities

None. The demo's existing no-argument behavior and the browser suite's fixture are unchanged baselines.

## Impact

`scripts/demo.py`, new `scripts/verify/` modules, Python and Node tests, `package.json`, the browser CI job and the development guide change. The wall server, page, hook handler and worker are used unchanged. No product UI, installation, runtime state, service, port or device is touched. Physical output and the live shared-input path are not claimed.
