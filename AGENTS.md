# Working on Codex Nanoleaf

This repository maps Codex task status to Nanoleaf Lines. A fresh Linux installation keeps its runtime and private state under `~/.local/share/codex-nanoleaf`. Legacy Windows installations use `%LOCALAPPDATA%\CodexNanoleaf`. Source delivery does not change either installation.

## Development

Before shared monitoring, MCP, controller APIs or collector migration, read
[the hub integration plan](docs/hub-integration.md) for ownership and the
canonical cross-repository contracts. The optional machine API adopts the shared
controller contract; Local MCP bindings adopt the shared module; shared monitoring remains planned. Read [the local MCP guide](docs/local-mcp.md) before changing that optional host. Before
controller API or credential changes, read [the controller API guide](docs/controller-api.md).

- Read `README.md` for setup and commands. Before changing lights, task allocation, hooks, or scene handling, read `bridge/README.md` for the existing behavior contract.
- Run `python3 scripts/check.py` from the repository root after Python changes. On Windows, use `python scripts/check.py`. The suite uses isolated state and must pass without a device or Codex credentials.
- After changing the map or its API, also run `npm run test:browser`. Use `python3 scripts/demo.py` for manual UI work. It uses synthetic tasks and never sends light requests.
- For changes to the tray or Windows installer, validate with Windows PowerShell. For Linux installer changes, exercise isolated Linux setup with fake device transport. Report separately whether Windows and physical-light checks ran; an isolated test does not prove a device update succeeded.
- After workflow, skill, or OpenSpec changes, run `npm run check:workflow` and `npm run test:workflow` from the root after `npm ci`. Both must exit zero. An empty specification inventory is allowed during bootstrap and must be reported as empty.

## Development workflow

- Codex and Claude Code share these repository rules. Each active deliverable has one coordinating writer, branch, and writable worktree. Before editing, identify the owner and inspect existing worktrees. Never edit, reset, rebase, or remove another session's worktree or branch. Follow [concurrent development](docs/sdlc.md#concurrent-development-and-handoffs) for claims, handoff, shared Git operations, and cleanup.
- For planning, implementation, and delivery, read [the SDLC guide](docs/sdlc.md). GitHub issues own requested outcomes, acceptance criteria, dependencies, and status here.
- Reuse installed skills from the shared `agent-skills` catalog. Follow this SDLC for ordinary implementation; use `plan-work` or `deliver-work` only when explicitly invoked. For unsettled decisions, compose `grill-with-docs`; for meaningful executable changes, compose `tdd`; for review, use `code-review`. [Shared skill setup](docs/development.md#shared-skills) names the source and required skills. Report missing prerequisites instead of copying skills into this repository.
- Keep only domain-specific skills with domain code. Reusable methods and OpenSpec integrations belong in `agent-skills`; domain contracts, verification commands, and policy remain here. This bootstrap needs no local skills.
- Planning-only and review-only requests remain read-only. Explicit planning-document requests authorize those documents only. Standalone documentation maintenance follows the delivery default unless the user requests local edits only.
- An implementation/delivery request normally includes issue updates, an isolated worktree, tests, PR publication, independent review, an eligible merge, and final readback. Narrower user instructions prevail. Routine authorized steps do not need repeated confirmation. Installation requires an explicit request.
- Deliver all repository changes through PRs; never push changes directly to `main`. A PR with UI changes requires explicit human approval of its current candidate before merge. Record that approval in the PR. Until approval arrives, finish checks and independent review, then leave the PR open for human review. Agent reviews and successful CI do not substitute for human approval; changed UI requires renewed approval.
- This repository deliberately composes the shared TDD and Grill with Docs methods. Their global explicit-only switches stay unchanged. Each substep preserves its own action boundary and returns to the authorized coordinator; it does not discard existing delivery authority.
- Run OpenSpec through `npm run openspec -- <arguments>` from the assigned worktree. Select the exact issue-linked change and local planning root. Use `init --tools none --profile core --no-animation` if initialization is needed; shared integrations are installed from the catalog separately.
- Before synchronization/archive, require complete applicable artifacts and tasks, acceptance evidence, and successful current input lookups. Verify every affected spec. A documented conditional design omission is valid; failed lookups and unfinished work are not. Complete synchronization/archive on the delivery branch before final review.
- The coordinator owns repository and GitHub writes. Obtain independent read-only Standards and Specification reviews against the same committed base/head. Follow [all merge criteria](docs/sdlc.md#review-and-merge), including every configured CI job, the head-commit guard, main CI, and issue readback. Missing independent review or CI prevents automatic merging.
- Preserve other worktrees and their installation owners. Source delivery does not install, alter lights, or clean up another task's branch.

## Runtime boundaries

- Keep one active installation and one light-writing worker per device. Fresh Linux hooks, CLI, wall map, and controller share Linux SQLite; MCP calls the controller over direct loopback HTTP. Legacy Windows installations retain Windows Python forwarding. Never share runtime SQLite across Windows and Linux, because their locks do not exclude each other. Before Linux setup or service work, read [the Linux installation guide](docs/linux-install.md) and its ownership/acceptance boundaries.
- Keep credentials, databases, live task metadata, scene state, hook files, and installed backups out of Git. The browser must never receive the Nanoleaf token.
- Preserve task pulse epochs, unread tracking, active comet source reservations, saved project preferences, and the user's mode and scene selection during changes.
- Read Codex metadata through the existing reader. Do not write Codex's internal SQLite database or mark tasks read from the map.
- Source changes and tests do not update the installed bridge. An explicitly requested fresh Linux installation may leave old Nanoleaf data unused; preserve unrelated hooks, applications, and Codex data. Stop the Windows owner before registering active Linux hooks or enabling services. For an authorized Windows upgrade, use `bridge/install-modes.ps1`, which backs up state and preserves tasks and trusted hooks. Read `docs/development.md` before installation or physical verification. Do not run fresh `setup` to upgrade an existing installation, because it clears task records.

## Code Review Rules

Flag competing light writers, credentials exposed to the browser or Git, loss of task/scene state, project reservations borrowed by unrelated projects, and animation changes that erase red/yellow alerts or restart completed comets. Review state migrations for backward compatibility and loss of user preferences.

## Human-facing prose

Use the centrally installed `$unslop` skill for the final editorial pass on commentary, responses, and documentation. Preserve facts, commands, contracts, and validation evidence. If it is unavailable, report that and continue without installing or copying it.

## Work guide maintenance

For every authorized delivery or planning change, read the
[shared guide maintenance procedure](https://github.com/jimmie-potts/agent-device-hub/blob/main/docs/work-guide/README.md).
The hub owns the cross-project HTML and its inputs. Coordinate a linked hub PR
that updates affected facts and records this delivery in
`docs/work-guide/updates.md`, or records a specific no-impact reason. Include
that PR and synchronization status in this repository's PR and completion report.
Pending guide synchronization remains unfinished delivery work. Read-only tasks
do not authorize writes, and guide maintenance does not authorize devices or hosting.
The shared skills consume that procedure at planning publication, candidate
review, verified completion and authorized public publication. Report guide-source
synchronization, public artifact publication and live verification separately,
with evidence or a pending owner/next action. Tracker-only requests change only
the tracker; a source merge does not update the public site.
