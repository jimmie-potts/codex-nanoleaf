## Context

See the proposal for scope. The encoder currently projects positions onto an axis or radius, then normalizes the span; wave and gradient reserve part of a cycle for that linear sweep. Circular directions need an angular phase independent of the wall's angular coverage. The schema's cross-module criterion applies to validation and MCP discovery.

## Goals / Non-Goals

Make both spatial patterns rotate around the saved centroid and add one faster timing step. Keep every existing direction and speed byte-identical. No new transport, writer, state or user interface is needed.

## Decisions

- Compute angle with positive Y pointing up, matching existing `up`. Counterclockwise follows increasing angle from the positive X axis; clockwise follows decreasing angle. Use a full turn rather than normalizing observed minimum/maximum angles, which would collapse opposite Lines onto the same phase.
- Use a complete cyclic color/crest phase for circular directions. Retain the existing three-quarter wave sweep and gradient color spread for all original directions.
- A Line at the centroid gets phase zero; coincident layouts remain deterministic. Custom centers stay deferred as the issue requests.
- `faster` uses one decisecond per base keyframe step. Existing pattern-specific multipliers and fixed one-decisecond flashes stay intact.

## Risks / Trade-offs

Twelve keyframes quantize nearby angles to the same crest frame; encoder tests allow ties and check circular phase error. Golden hashes captured before production edits protect old payloads on both fixture layouts. Existing Free gating, bounds and uncertainty tests protect the unchanged admission path.

## Migration Plan

No state migration. Deliver source through the coordinated PR sequence; installation and physical acceptance remain excluded.
