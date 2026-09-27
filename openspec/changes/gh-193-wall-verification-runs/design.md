## Context

See proposal.md. The change adds a new external dependency (the Hub's app verification core, vendored as a release archive), a process-wide security boundary and a new test harness, which meets the schema's design criteria.

## Goals / Non-Goals

Run the actual wall server, page, state store, hook handler and allocation over synthetic state, prove that no device, installed service or new process can be reached, and make a known-wrong result fail its capture. The run lifecycle (supervisor unit, lease, receipt, proof, card, reseed) stays in the shared core. No light uploads, layout discovery from a device, shared-input cutover, runtime migration, new wall editor or product UI change.

## Decisions

**Boundary by audit hook plus the request seam.** The wall server already takes a `request` seam for device reads and a `launch` seam for waking workers. The run passes a recording trap for `request` and the worker stand-in for `launch`. Because a future code path could bypass either seam, each entry point also installs `sys.addaudithook` and refuses `socket.connect`, `socket.sendto`, `socket.sendmsg` and process creation events. The wall server only accepts connections, so it needs none of them. The refusal subclasses `ConnectionRefusedError`, so product code treats it as an unreachable device and keeps serving; the recorded log, not a crash, is the evidence. Resolver traffic inside libc is not intercepted; no Nanoleaf path resolves a host name.

**Start like the installed map.** `serve` loads the configuration and ensures geometry with the trap, as `wall_server.serve` does, and writes `map-server.json` with its port and instance. The readiness probe matches that instance against `/health`, so another listener on the port cannot pass. The no-argument demo uses the same path over a temporary reference state.

**Reseed by relaunch.** The core stops the application, empties its data directory, seeds and relaunches on the recorded port. The demo therefore needs no in-place reseed. A relaunch generates a new per-process edit token.

**Transitions through the hook handler.** `drive` applies synthetic hook events with `bridge.handle_event` and the worker stand-in, as a real hook does with a real worker. Defect transitions are wrong inputs that produce a known-wrong state.

**Assertions on painted and listed output.** Steps read the Prism SVG fills, the task list badges, the readout and the renderer snapshot. A presentation negative control serves the page with one exact source replacement; the step first asserts that the replacement happened once, so a stale mutation fails loudly rather than passing.

## Risks / Trade-offs

- An audit hook cannot be removed: tests install it only in child processes.
- The page-mutation control depends on one line of `bridge/wall.html`: a refactor makes that control fail at its injection assertion, which is the intended signal to update it.
- Steps change state: each runs on a freshly seeded run.
- Physical accuracy is out of scope: the stand-in never renders.

## Migration Plan

Source delivery changes no installation. Runs live under the core's runtime root and proof under the canonical checkout's ignored evidence directory.
