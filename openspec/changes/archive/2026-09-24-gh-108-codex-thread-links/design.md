## Context

See proposal.md for scope. The wall builds task dictionaries independently of the machine APIs. Shared task keys are hashes; the retained envelope and existing presented-root grouping retain their raw identities. Legacy metadata already refreshes the configured title index. This design records the cross-module privacy boundary.

## Goals / Non-Goals

Use only an eligible presented task's identity for navigation. Keep URL construction on the server and outside persistent task data. No custom browser action handler, new read acknowledgment, remote host routing or device operation is needed.

## Decisions

- Derive shared eligibility using the existing presented-root mapping from the stored accepted envelope. Do not infer raw UUIDs from hashed keys or choose a child: both could open the wrong conversation.
- Validate UUID syntax before concatenation. Do not accept arbitrary paths, query strings or protocols. Use only the local `codex://threads/` form.
- Qualify legacy tasks through the configured title index, not cached task titles or project membership. Track current index membership separately from retained title text so removal or a missing index suppresses links while title recovery behavior remains intact.
- Add the URL at the wall projection boundary, leaving machine API whitelists and shared contracts unchanged. A schema migration or stored URL would duplicate derivable data.
- Render a native anchor and include `codexUrl` in the card fingerprint. Existing selection and override controls retain their behavior. No link belongs in task rows.

## Risks / Trade-offs

- The internal Codex URI format can change. Validate one real Windows navigation separately; automated tests establish construction and browser semantics only.
- Missing index data must not qualify legacy tasks from stale titles. Fail closed on unavailable index reads; restore links on a later successful refresh.
- Shared identity depends on the accepted owner snapshot and its Desktop session-ID assumption. Preserve that explicit rule without expanding host qualification scope.

## Migration Plan

No stored-data migration or installation is part of this source change. Reverting the source removes the optional link. Windows acceptance uses isolated demo state and never starts a device worker.
