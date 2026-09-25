## Context

`check_envelope` validated the feed and then rejected it if any session's source was undeclared. Every consumer of the projection reads the envelope stored by `_project`: the wall map, the integration API, eviction, inspection and the prior-snapshot comparison in the next projection.

## Goals / Non-Goals

**Goals:** skip undeclared sessions without affecting declared ones; report them in `shared-status`; keep whole-snapshot rejection for envelope failures.

**Non-Goals:** configuring sources while shared input is selected; installing Claude Code hooks; any hub change.

## Decisions

- **Filter at projection, not validation.** `check_envelope` validates only. `_project` removes undeclared sessions before grouping and stores the filtered envelope with a local `skipped` summary. Because every downstream reader uses the stored envelope, none can present, evict or group a skipped session. Filtering inside `check_envelope` was rejected: it runs twice per poll, so the second pass would lose the skipped count.
- **Acknowledgment filters its fresh fetch** with the same helper, so a skipped session's notice is `notice-unavailable`.
- **Declaring later needs no new replay guard.** Configuration is refused while shared input is selected, and it clears the stored envelope. The following `shared-select shared` projects with resync, so existing sessions get expired wave epochs and no comets.
- **Grouping.** The pinned agent-state contract requires a parent and its subagents to share one source, so skipping a source removes whole groups. Grouping runs only over declared sessions; if the contract ever allowed a cross-source parent, a declared child would follow the existing missing-parent rule.

## Risks / Trade-offs

- **Stored state shape.** The stored envelope gains a local `skipped` key. Envelopes stored before this change lack it and never held undeclared sessions, so inspection defaults to zero. Older code ignores the key. No migration or preference change is involved.
- **Silent omission.** A misconfigured source now leaves its tasks off the wall instead of stopping it. `shared-status` names the skipped sources so the operator can declare them.
