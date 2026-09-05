# ADR 0001: GitHub development workflow

Status: Accepted

Date: 2026-09-05

## Context

Codex Nanoleaf has isolated Python tests, browser checks, Windows validation, and
a separate private installation. It needs a repeatable way to define and deliver
work without importing another project's Jira policies or changing live lights.
The repository is private and its current GitHub plan limits native branch
protection. The user approved the choices below in the SDLC setup plan.

## Decision

- GitHub issues own requested scope, acceptance criteria, dependencies, delivery
  target, and status. Use issue labels rather than a Project board.
- Use one independently deliverable issue, isolated worktree, and PR by default.
  All repository changes go through PRs, with no direct changes to `main`.
  Keep implementation, tests, documentation, and applicable spec/archive changes
  together. Close the issue after merged-source CI succeeds, or after the stated
  installation target is verified when that was included.
- Adopt OpenSpec 1.12.0 and its standard schema incrementally. The bridge guide
  remains authoritative for behavior without a migrated capability spec.
- Use TDD for meaningful executable behavior. Record real red/green evidence,
  and explain a proportionate substitute when a failing automated test is
  impractical. Documentation and cosmetic changes need relevant inspection.
- Route automatically to shared workflows within the user's requested
  scope. Planning and review remain read-only. Authorized implementation normally
  continues through an eligible merge without repeated permission questions.
- Require independent Standards and Specification review and successful current
  CI before automatic merge. Fix P0-P2 defects, document P3 dispositions, and
  revalidate changed candidates. The active agent squash-merges with a head-SHA
  guard and never bypasses protections.
- Require explicit human approval of the current candidate for every UI PR.
  Record approval in the PR, and obtain renewed approval when its UI changes.
  Agent review and CI remain required but do not replace the human decision.
- Keep installation and physical verification separate and explicitly requested.
  Preserve the current installation owner and single Windows light writer.
- Maintain reusable skills in `agent-skills`, including planning, TDD, review,
  delivery, and OpenSpec integrations. Reuse existing definitions and install
  them through the shared catalog. Keep only domain-specific skills in a domain
  repository; this bootstrap needs none. This revises the initial proposal to
  commit generated integrations and Nanoleaf-named workflow wrappers here.
- Validate the workflow with isolated exercises. Preserve unrelated catalog
  work, global OpenSpec configuration, product behavior, and live installation.
  Do not create background services.

## Consequences

GitHub, specification files, decisions, and PR evidence have distinct owners.
Small changes use less planning than features and migrations. Reviewed specs
replace documentation contracts one capability at a time.

The merge checks depend on the active agent following the documented procedure
while native protection is unavailable. They are not a server-side restriction.
Missing review or CI leaves work open. Skills must preserve scope across handoffs;
shared methods return to the authorized coordinator, and repository policy
controls required completion evidence. Shared skill updates have their own
review and source history; consumers record the evaluated revision.

The [SDLC guide](../sdlc.md) owns the operating procedure. Changes to these lasting
defaults should amend this decision through review or introduce a superseding ADR.
