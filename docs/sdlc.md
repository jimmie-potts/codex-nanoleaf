# Development workflow

Use a GitHub issue to define a deliverable, develop it in an isolated worktree,
and merge one reviewed PR when its acceptance evidence and CI pass. Repository instructions route the agent to the relevant shared skills. The user can narrow any
task to planning, local changes, review, or a ready PR.

All repository changes must be delivered through PRs. Do not push changes
directly to `main`. PRs that change the UI also require explicit human approval
of the current candidate before merging. Finish implementation, checks, and
independent review, then leave the PR open while that approval is pending.

## Authority and information ownership

| Information | Owner |
| --- | --- |
| Reusable skill methods and OpenSpec integrations | [Shared agent-skills catalog](https://github.com/jimmie-potts/agent-skills) |
| Requested outcome, scope, acceptance criteria, dependencies, delivery target, status | GitHub issue |
| Current capability requirements after migration | `openspec/specs/<capability>/spec.md` |
| Current behavior not yet migrated | [Bridge guide](../bridge/README.md) |
| Proposed requirement changes and implementation tasks | The issue-linked OpenSpec change |
| Lasting decisions and their rationale | [Decision records](decisions/0001-development-workflow.md) |
| Development, installation, and recovery commands | [Development guide](development.md) |
| Reviewed revisions, test evidence, CI, findings and dispositions | Pull request |

Link between owners. Do not maintain a second copy of issue acceptance criteria
in OPSX or a second status ledger in a document. Translate issue outcomes into
testable specification scenarios and link each scenario back to its criterion.
When sources disagree, surface the conflict and resolve it before dependent work.

Planning-only and review-only requests are read-only, including GitHub. A request
to write specified planning documents permits those edits, but does not start
implementation. An implementation or delivery request normally includes issue
tracking, worktree creation, code and documentation changes, tests, PR publication,
review fixes, an eligible merge, final readback, and
[cleanup after delivery](#cleanup-after-delivery). Existing authority carries
across skill handoffs. A skill does not grant new authority or bypass host
permissions. Ask only for unresolved decisions or actions outside that scope.

Standalone documentation maintenance follows that delivery default. For example,
correcting an existing setup command includes the issue and PR workflow unless
the user requests local edits only. Preparing planning documents during a design
discussion stays within the planning boundary.

Installing the Windows bridge or changing physical lights needs an explicit
request. Keep source, installed, and physically verified claims separate.

## Define and prepare work

Search existing issues before creating one. Draft features with the prompts in
[scope defaults](#scope-defaults) and bugs with the bug form. For maintenance
and investigations, use the same headings in an ordinary issue. Source-only is
the default delivery target.

Preserve unrelated labels. Use `bug`, `enhancement`, `documentation`, or
`maintenance` to describe the work, with exactly one status label on an open
delivery issue:

| Label | Meaning |
| --- | --- |
| `status:backlog` | Recorded work that is not ready to implement |
| `status:ready` | Observable criteria, known dependencies, and settled implementation-changing decisions |
| `status:in-progress` | Implementation or validation is underway |
| `status:review` | A PR is undergoing review and final validation |

Add `blocked` independently when progress needs a dependency, decision, or
unavailable required verification. Describe the reason and next action in the
issue. Remove it when the condition clears. Replace only status labels during a
transition. After issue closure, remove all `status:*` labels and `blocked` while
preserving descriptive labels. No Project board, status bot, or scheduled service
is required; the delivery agent performs and reads back these updates.

Use `research` or `openai-docs` for source-dependent facts, `how` to understand
current code, `why` for historical rationale, and `diagnosing-bugs` for an unknown
failure. Use `codebase-design` for interface or module decisions. Investigation
ends with findings and a recommended next step; it does not imply a fix.

Use the shared `grill-with-docs` method when choices could change what is built. Investigate
discoverable facts first, then ask all independent current questions together.
Resolve dependent questions in later rounds. Record accepted decisions and
assumptions. Add an ADR for lasting choices about ownership, compatibility,
concurrency, persistence, or deployment. Routine implementation details need no ADR.

## Scope defaults

This is a personal project. Size each story for how it actually runs: one
operator, the selected installation (the Linux runtime, with legacy Windows
installations still supported where documented), and the Nanoleaf devices
explicitly registered there. Add hosts, users, services or automation only when
the story needs them. These defaults never remove an already accepted capability.

Assess scope when drafting a story, at pickup and after a material scope or
assumption change, whether or not `plan-work` or `deliver-work` was invoked.
Use the shared assessment in the installed deliver-work package's
`references/work-assessment.md`, found through the host's skill discovery.
Reading it does not invoke either skill. If it is unavailable, report that and
apply this section. Codex and Claude follow the same policy. A read-only request
reports the assessment instead of editing the issue.

Draft stories with the five prompts of the
[feature form](../.github/ISSUE_TEMPLATE/feature.yml). A small story may answer
them in a few sentences.

1. Outcome and real setup.
2. Smallest useful implementation, with dependencies.
3. Behavior and protections to preserve.
4. Observable acceptance and planned evidence, with the delivery target.
5. Meaningful deferrals, each with its consequence or manual alternative and
   its owning issue or revisit trigger.

Prefer existing components and explicit manual steps where practical. Avoid
speculative platform support, abstraction layers, automatic rollback systems and
broad outage matrices. Always protect supported behavior: one authoritative
state owner and one light writer per device, correct targets, bounded queued
work, no unsafe replay, accurate freshness and completion, manual control, and
user data integrity, including task and scene state.

Basic credential hygiene and the existing authorization and origin checks apply
to local use too. Reassess before remote or public exposure, an additional
operator or writer, expanded compatibility, or recurring failures. A change that
could lose irreplaceable data needs practical recovery evidence, using existing
facilities where possible; this is not a general backup-tooling requirement.

For each meaningful cut, name the capability or assurance lost and reconcile
dependent issues and specifications within the task's authority. Never silently
remove requested behavior; ask the user when a cut would change it. Scope
defaults keep review, CI, UI approval, OpenSpec and the source, installation and
physical boundaries, with their existing exceptions, and add no new gate.

For a consequential change to credentials, persistent state, concurrency or
device commands, define acceptance examples before implementation. Give the owner
a short walkthrough in the PR with code and test links: state and writer
ownership, timeout, restart and duplicate behavior, the important failure test,
and diagnosis and recovery. Explain any change that weakens an existing test
assertion. The walkthrough is an understanding aid, not an approval gate.

Judge these defaults from existing PR evidence: delivery time, correction rounds,
defects after merge and human effort. Unknown effort or usage stays unknown.
[agent-skills#44](https://github.com/jimmie-potts/agent-skills/issues/44) owns
the comparative evaluation; no metrics service or parallel report is required.

Example, checked on 2026-09-24 against the map selector
([#44](https://github.com/jimmie-potts/codex-nanoleaf/issues/44)) and the future
combined pool ([#47](https://github.com/jimmie-potts/codex-nanoleaf/issues/47)):

- Setup: one operator, the Linux installation, and registered Lines and Light
  Panels.
- Smallest implementation: a selector in the existing map that shows one device
  at a time, with static triangle colours.
- Preserve: the protected controller API stays Lines-only, requests that name
  no device still address Lines, unknown devices are rejected, and selection
  sends no Locate. Origin and edit-token checks remain.
- Evidence: browser fixtures with Lines and the synthetic NL22 layout, plus
  human approval of the UI candidate.
- Deferred: the combined pool and its migration of tasks, unread evidence,
  preferences and effect epochs stay with #47 rather than entering the selector.
  Side-by-side devices and triangle animation wait for a user request.
- Limitation: this checks the issue text against the guidance. It does not show
  how an agent will apply it.

## Choose the amount of planning

| Work | Required planning |
| --- | --- |
| Small fix restoring an existing contract | Issue, reproduction, focused test; explain why no spec delta is needed |
| Feature or changed contract | Issue plus OPSX proposal, capability deltas, and tasks |
| State migration, concurrency, installer, or significant design change | The applicable change plan, failure/recovery cases, and a design; ADR if the choice has lasting consequences |
| Documentation or maintenance without a behavior delta | Issue and PR; record the reason OPSX is unnecessary |
| Uncertain feasibility | Bounded investigation with a question and a stop condition |

Use OpenSpec's standard `spec-driven` schema. A design document is conditional on
the schema's published criteria; when omitted, record the reason and verify all
other required artifacts. Every task names how its completion can be observed.
File existence and checked boxes alone do not prove that behavior works.

In OpenSpec 1.12.0, a valid conditional design omission can leave
`isPlanningComplete: false` and `design: ready` while apply reports `ready` or
`all_done`. Check the required artifact set and the recorded omission; do not
use that status flag alone to decide readiness or completion.

Use `gh-<issue-number>-<slug>` for a change identity, and link the exact issue in
its proposal. Reuse an existing linked change, checking both active and archived
directories for collisions. Do not choose the newest or only active change as a
substitute for identifying the requested issue. An already-delivered change is
history; further work needs a new scoped issue/change.

Adopt capability specifications incrementally. Before the first change to an
unmigrated capability, identify its contract in the bridge guide and tests. Put
the retained requirements and proposed delta under review together, distinguish
unchanged behavior from the requested addition, and update the guide's links.
Remove competing normative text for the migrated capability. All other behavior
continues to use the existing guide. The tooling bootstrap intentionally starts
with zero capability specs; that is not evidence of a formal behavior baseline.

## Implement and verify

Start a branch named `codex/gh-<issue-number>-<slug>` in its own worktree from
refreshed `main`. Record the base revision and inspect existing worktrees before
editing. Preserve their state. Map dependencies before delegating. The
coordinating agent owns repository and GitHub writes; review agents return
findings and evidence without changing the candidate.

For each executable behavior, use the shared `tdd` method: select an acceptance scenario,
run a focused failing test, implement the smallest useful change, rerun that test,
and refactor while keeping it green. Use the existing fake clock, isolated SQLite
state, and fake controller where they fit. Keep the actual pre-fix command and
failure reason in PR evidence. Never invent a red result after implementation.

An impractical automated reproduction may use a focused executable script,
browser scenario, or other observable check. Explain the limitation before
changing production code and record the substitute evidence. Do not create a
large harness, brittle timing test, or test of wording merely to satisfy TDD.

Run the commands in [the development guide](development.md). Run the full Python
suite after Python changes, browser checks after map/API changes, and workflow
checks after skill/OPSX changes. Windows and hardware checks depend on the changed
behavior and issue target. Run relevant checks after fixes; repeat broader checks
only when changed code, failures, or unresolved concerns justify them. Required
CI still runs for every PR.

If implementation changes an assumption that affects scope or acceptance,
resolve that decision before proceeding. Update affected plans and tests before
claiming completion. Unrelated improvements belong in another issue.

## Concurrent development and handoffs

Codex and Claude Code use the same issue, review, and delivery policy. Each
active deliverable has one coordinating writer, an issue-based branch using
`codex/gh-<issue-number>-<slug>` regardless of tool, and an isolated writable
worktree. Read-only reviewers may inspect that candidate. Two writers must not
share a worktree, branch, or issue/PR coordinator role at the same time.

Before implementation, read the issue's current comments and status, inspect
`git worktree list --porcelain`, and check the intended path's branch, HEAD, and
dirty state. Record the coordinator/session, worktree path, branch, base SHA,
and intended scope in the issue. Reread the claim before editing. An existing
owner or competing claim requires an explicit handoff or a separately scoped
issue before writes. An issue comment is a coordination record, not an atomic
lock; agents must settle conflicting claims rather than assume the latest wins.

Worktrees share Git refs and configuration. Only the coordinator changes its
issue/PR, branch, or worktree registration. Avoid repository-wide configuration,
pruning, resets, or cleanup that could affect another owner. Each worktree owns
its dependencies and test artifacts; demos use separate ports and temporary
synthetic state. Never point development exercises at the installed bridge.

Serialize merges across deliverables. Record who owns the merge checkpoint in
the active issue, check other in-progress/review issues for a competing merge,
and resolve any overlap before continuing. A checkpoint covers the final
scope/base/head checks, merge, and main CI readback. Release it with the result
in the issue. If `main` advances, refresh affected evidence under the existing
merge rules before retrying. These records are procedural safeguards, not a
distributed locking service.

For a handoff, the outgoing writer stops mutations and records the worktree,
branch, HEAD, dirty/untracked files, running processes, evidence, and remaining
work in the issue or PR. The incoming writer confirms that state and accepts
ownership before editing. Retain uncommitted work in place; do not silently
stash, reset, or overwrite it. Shared personal memory is context, never a claim
or a substitute for current GitHub and Git evidence.

### Cleanup after delivery

Only the owner cleans up, and only what its delivery created. Start once
review-and-merge step 7 has confirmed that main CI succeeded and read back the
issue state, and any handoff has ended. Cleanup does not wait for installation
or physical checks unless they still use the worktree.

1. Confirm the PR is merged and the delivery worktree's `HEAD` is the PR's
   reviewed head (`headRefOid`, the `--match-head-commit` value), not the squash
   commit on `main`. Squash merges leave a branch's commits off `main`, so judge
   delivery by the PR's merged state, never by commit ancestry. Commits after
   the reviewed head are unfinished work.
2. Check running sessions and processes, tool-managed retention, and
   `git status --short --ignored` in the worktree, and look inside the scratch
   folder. `git worktree remove` deletes ignored files, including the worktree's
   own `.local/`, local configuration, databases and `node_modules/`. Move
   anything the issue still needs into the PR, the issue, or the canonical
   checkout's `.local/evidence/gh-<issue-number>-<slug>/`. The PR and issue are
   public, so private material goes only to `.local/evidence/`. Confirm the
   other ignored files are disposable.
3. In every case, clean up the canonical checkout's
   `.local/scratch/gh-<issue-number>-<slug>/` folder: remove each worktree
   registered inside it with ordinary `git worktree remove`, confirm that
   `git worktree list` shows none there, then delete the folder. Step 1's `HEAD`
   check applies only to the delivery worktree.
4. For a delivery worktree created with `git worktree add`, run ordinary
   `git worktree remove <owned-path>` from the canonical checkout and confirm
   with `git worktree list` that the path is gone. Do not delete the delivery
   branch yourself.
5. Leave a tool-managed worktree, such as a Claude Code worktree under
   `.claude/worktrees/` or a Codex-managed worktree, to that tool's own exit
   flow instead of `git worktree remove`; that flow may also delete its branch.
   Once steps 1 and 2 pass on a clean worktree, accepting the tool's option to
   discard the squash-merged commits is allowed. If this session cannot run that
   flow, keep the worktree and report it as ready to remove.

Keep the worktree and scratch, and report the path and reason, when a worktree
is dirty or locked, another process or session uses it, the delivery worktree's
`HEAD` differs from the reviewed head, evidence is not yet preserved, an ignored
file is not confirmed disposable, or `git worktree remove` refuses. Without the
user's explicit approval, never force removal or reset, clean, or discard files
to make a worktree removable. Never prune another owner's registration. If main
CI fails, or the work failed or was abandoned, ask the user whether to keep or
remove it and keep it until they decide. The
[Claude setup guide](claude-code.md) and
[Codex setup notes](../.codex/README.md) cover their different lifecycles.

## Review and merge

1. Complete the implementation, documentation, acceptance checks, and all
   applicable OPSX artifacts/tasks. For OPSX work, fetch current status and
   artifact/archive instructions through the local wrapper, require successful
   lookups, and verify the complete expected capability set. Synchronize and
   archive on the same branch before final review. Compare every affected main
   spec with its delta, then run `npm run check:workflow`. Shared skill defaults do not override these
   repository completion requirements.
2. Commit the full candidate and publish its PR. Use `Refs #<issue>` rather than
   an auto-closing keyword so the issue can remain open until main CI passes.
   Record the base SHA, head SHA, merge-base, diff command, and clean worktree
   state. Keep revision-dependent evidence in the PR, not in a file that would
   change the revision it describes.
3. Request independent read-only Standards and Specification reviews against
   that same fixed comparison. Each reviewer gets the issue, applicable sources,
   and its own rubric. Use the `code-review` method with GitHub as scope owner;
   other projects' Jira/Sprint Work assumptions do not apply. Separate fresh
   review agents may run in parallel. Without independent review, leave the PR
   open and mark the issue blocked; a self-review is insufficient for auto-merge.
4. Fix P0-P2 defects and ask the reviewer to reassess disputed findings with the
   evidence. Record P3 dispositions; link a follow-up issue when work is deferred.
   Read all GitHub review pages, including unresolved threads and current review
   decisions. Resolve threads after fixing or agreed disposition. Do not dismiss
   an outstanding change request merely to enable merge; obtain its resolution.
5. Require success for every configured Depot CI job. The current `Checks`
   workflow in `.depot/workflows/ci.yml` runs five Linux jobs: Workflow checks,
   Python 3.12, Python 3.14, Wall map browser checks, and MCP source checks.
   Inspect the workflow at the candidate revision for any changed job set. Use
   the latest Depot run attributable to that candidate, confirm its PR
   association/head SHA, inspect every job, and read all result pages. The
   disabled GitHub Actions workflow and its historical runs are not evidence.
   Missing, failed, cancelled, skipped, or pending required jobs are not success.
   Do not use an empty `--required` check list as proof on an unprotected branch.
6. Immediately before merging, reread issue scope, dependencies, head revision,
   and current `main`. If the head or base changed, refresh the comparison and
   affected tests/reviews/CI. Require no unresolved decisions, blocking findings,
   or outstanding change requests. For a UI change, also require explicit human
   approval of the current candidate, recorded in the PR. Agent review and CI
   do not satisfy this gate; changed UI requires renewed human approval. Keep
   the PR and issue open in review while approval is pending. Merge only the reviewed head:
   `gh pr merge <number> --repo jimmie-potts/codex-nanoleaf --squash --match-head-commit <reviewed-head>`.
   Never use `--admin`. Do not delete another worktree or its branch.
7. Read back the PR's merged commit and verify it is on `main`. Check the push
   Depot CI run for that merged revision and every configured job. Close a source-only
   issue only after success, then read back closure and label cleanup. Keep the
   issue open and blocked if post-merge checks fail or required installation work
   remains. Report the failing evidence and next action.
8. Clean up this delivery's own worktree and scratch as described in
   [Cleanup after delivery](#cleanup-after-delivery).

This repository is public. Native branch protection is available, but `main` has
no branch protection or rulesets configured, so these agent checks are
procedural safeguards, not server-enforced protection. Delivery work does not
change visibility, the GitHub account plan, or existing merge-method settings.
The active delivery task performs the checked merge; no background merge service
or native auto-merge dependency is introduced. Honor any protections added
later.

## Completion and installation handoff

Record source revision, local checks, local Windows checks, and
installation/physical status separately. Hosted CI has no Windows jobs. An
installed-feature issue remains open until its requested checks are satisfied.
Source-only work does not invoke the installer. For an authorized upgrade,
follow [the existing deployment procedure](development.md#upgrade-the-installed-integration)
and coordinate with the installation owner. Preserve live tasks, scene choices,
and the single Windows light writer.

## Examples

- **Bug:** Duplicate completion events queue two comets. Link the existing
  contract, reproduce the duplicate with the fake clock/device, fix it, and show
  the same test passing. An unchanged contract needs no OPSX delta.
- **Feature:** A requested new allocation rule changes which waiting task gets a
  Line. Settle eligibility and ordering, write capability scenarios, implement
  one scenario at a time, and review the synchronized spec with the code.
- **Documentation:** Clarify the existing upgrade command. Use a documentation
  issue and a small PR, verify commands and links, and record source-only delivery.
- **Investigation:** Determine whether a controller capability can support a
  proposed effect. Gather permitted documentation or isolated evidence, report
  feasibility and unknowns, and stop at the requested research boundary.

## Maintaining the workflow

The accepted defaults are recorded in [ADR 0001](decisions/0001-development-workflow.md).
Maintain reusable skill definitions in the shared `agent-skills` repository.
Use existing planning, TDD, and review skills; keep reusable delivery and OpenSpec
procedures there too. This repository owns Nanoleaf contracts, commands, and
GitHub policy through `AGENTS.md`, this guide, and project configuration. Only a
procedure that depends on the Nanoleaf domain belongs in a local skill. This
bootstrap has none.

Install shared skills as described in [the development guide](development.md#shared-skills).
Use `plan-work` and `deliver-work` only when explicitly invoked; ordinary work
follows this SDLC. When a task intentionally updates or publishes the
cross-project guide, follow [its procedure](#cross-project-work-guide). When
`plan-work` or `deliver-work` is invoked, its documentation checkpoints use that
section; ordinary work has no guide obligation to record.
Do not vendor copies, renamed wrappers, or external symlinks into this repository.
Review shared skill changes in their owning repository and record the evaluated
catalog revision in PR evidence. Updating OpenSpec integrations is a catalog task;
initialize this project's specification storage without generating integrations.

Validate meaningful workflow behavior using temporary fixtures. Keep credentials,
real task metadata, and device state out of them. Test planning-only requests,
automatic routing, bug/feature TDD, and rejection of stale review, missing CI,
unresolved findings, unfinished archives, and unavailable independent review.
Record the observed outcomes in the PR. Do not claim GitHub writes were tested
when an exercise only simulated their evidence.

Sources: [OpenSpec 1.12.0 CLI](https://github.com/Fission-AI/OpenSpec/blob/v1.12.0/docs/cli.md),
[OpenSpec Codex integration](https://github.com/Fission-AI/OpenSpec/blob/v1.12.0/docs/supported-tools.md),
[OpenAI Docs skill](https://github.com/openai/skills/blob/main/skills/.curated/openai-docs/SKILL.md),
[OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model),
and [GitHub branch protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

## Cross-project work guide

The [hub work guide](https://github.com/jimmie-potts/agent-device-hub/blob/main/docs/work-guide/README.md) is a dated
publication of remaining work, history and architecture for these projects.
GitHub issues remain authoritative for scope and status, and the guide is not a
live status claim. The hub owns the guide's inputs, generated HTML and
maintenance procedure.

Ordinary planning and delivery have no guide obligation. They do not refresh
the guide, open a companion hub PR, write a no-impact entry, or check public
currency. The hub retired its `docs/work-guide/updates.md` ledger; Git history
and PRs keep that record.

When a task's authorized scope intentionally updates or publishes the guide,
follow the hub procedure. The task's coordinator owns the linked hub PR and any
separately authorized public publication. Link the hub PR from this
repository's PR. If the authorized guide revision must include merge or
acceptance facts that were unavailable before merge, reconcile them in a linked
follow-up. Report source completion, guide revision, public publication and live
verification separately, each with evidence or a pending owner and next action.
Keep installation, client and physical evidence as separate claims. These rules
grant no authority for read-only tasks, tracker changes, installation or
deployment.
