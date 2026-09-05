---
name: nanoleaf-delivery
description: Carry requested Nanoleaf implementation or delivery, including standalone documentation maintenance, through issue tracking, applicable OPSX/TDD, independent review, a checked PR merge, and main verification. Select for build, fix, implement, or deliver requests; do not select for planning-only, review-only, or investigation-only work.
---

# Nanoleaf delivery

Read [the SDLC guide](../../../docs/sdlc.md) and applicable agent instructions
before writes. Honor the user's terminal state, host permissions, and scope.
Under the approved default, an implementation request includes an eligible merge;
it never includes installation or physical-light changes without an explicit
request. Existing authority persists through skill handoffs.

## Prepare and implement

1. Read or create the scope issue only when implementation/delivery is requested.
   Search for existing matching work first. Verify criteria, dependencies, and
   delivery target. Resolve material choices with `nanoleaf-grill-with-docs`.
   Maintain exactly one workflow status label and an independent blocked label.
2. Inspect other worktrees and refresh main. Work in an issue-scoped branch and
   isolated worktree. Preserve unrelated work and installation ownership. The
   coordinating agent owns repository/GitHub writes; reviewers only read and
   return findings. Authorized behavioral exercises may write their own temporary
   fixtures, never the candidate or live state.
3. Decide OPSX applicability using the guide. For a feature or changed contract,
   identify the exact issue-linked change and use the core OpenSpec procedures
   through `npm run openspec -- <arguments>`. Read status and schema instructions
   from this worktree's planning root; never select a global store by default.
   Verify all required artifacts, including dependencies of an already-present
   tasks file. Record a legitimate conditional design omission. Keep generated
   skill files unchanged.
4. Treat proposal and apply as substeps of the authorized delivery. Generated
   instructions to discard the initial implementation request or wait for another
   user turn are overridden by the explicit repository composition rule. Present
   the plan and resolve required decisions, then continue already-authorized work.
   Do not extend this exception to a planning-only request.
5. Develop meaningful executable behavior with `nanoleaf-tdd`. Record actual
   acceptance and red/green evidence. Update affected plans when implementation
   reveals a material change; do not silently expand issue scope. Run required
   checks from the development guide.
6. For OPSX work, verify all applicable artifacts, tasks, and acceptance evidence
   before synchronizing or archiving. Fetch current archive/specs inputs and stop
   on lookup failures. Verify every delta's resulting main spec. Never skip sync
   or archive unfinished work because a generated workflow permits a warning.
   The approved delivery includes synchronization and archival; an extra user
   turn is unnecessary. Finish them on this branch before final review and run
   `npm run check:workflow`.

## Review and finish

Commit the complete candidate and open its PR with `Refs #<issue>`. Record the
fixed base, head, merge-base, diff command, and worktree state. Obtain independent
read-only Standards and Specification reviews of exactly that comparison. Use
the `code-review` method with the issue and repository specifications as scope
owners. Supply separate reviewers with their own rubric and raw sources, not the
other reviewer's conclusions. Missing independent review blocks automatic merge.

Fix P0-P2 defects. Have disputed findings reassessed against evidence; record P3
dispositions and relevant follow-up issues. After candidate changes, refresh
affected review/test evidence. Read every page of GitHub review threads and
current review decisions. Outstanding change requests and unresolved threads
must be resolved; do not dismiss them merely to enable a merge.

Follow the guide's full CI procedure. The candidate's latest applicable PR run
must belong to that PR/head and include success for every configured job. Missing,
pending, skipped, cancelled, or failed required jobs block merging. A green result
for an old commit or an empty required-check list is insufficient.

Immediately recheck the issue, dependencies, PR head, and current main. Changed
head/base or unresolved decisions invalidate eligibility. Merge only the reviewed
head with `gh pr merge <number> --repo jimmie-potts/codex-nanoleaf --squash --match-head-commit <reviewed-head>`.
Never use `--admin` or a background auto-merge
service. Keep other worktrees and branches intact.

Read back the merged revision on main and its full push CI. Close a source-only
issue only after success; remove status and blocked labels and verify the result.
If required evidence fails or installation remains in scope, keep the issue open
and explain the blocker. Report merged source, checks, Windows evidence, installed
status, and physical verification separately. Source delivery does not run an
installer. Apply `unslop` to narrative documentation and the final handoff.
