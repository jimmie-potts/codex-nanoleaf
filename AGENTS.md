# Working on Codex Nanoleaf

This repository is the source for a Windows bridge that maps Codex task status to Nanoleaf Lines. The installed bridge and its private state live separately in `%LOCALAPPDATA%\CodexNanoleaf`.

## Development

- Read `README.md` for setup and commands. Before changing lights, task allocation, hooks, or scene handling, read `bridge/README.md` for the existing behavior contract.
- Run `python3 scripts/check.py` from the repository root after Python changes. On Windows, use `python scripts/check.py`. The suite uses isolated state and must pass without a device or Codex credentials.
- After changing the map or its API, also run `npm run test:browser`. Use `python3 scripts/demo.py` for manual UI work. It uses synthetic tasks and never sends light requests.
- For changes to the tray or installer, validate with Windows PowerShell. Report separately whether Windows and physical-light checks ran; an isolated test does not prove a device update succeeded.
- After workflow, skill, or OpenSpec changes, run `npm run check:workflow` and `npm run test:workflow` from the root after `npm ci`. Both must exit zero. An empty specification inventory is allowed during bootstrap and must be reported as empty.

## Development workflow

- For planning, implementation, and delivery, read [the SDLC guide](docs/sdlc.md). GitHub issues own requested outcomes, acceptance criteria, dependencies, and status here.
- Reuse installed skills from the shared `agent-skills` catalog. For implementation, select `github-delivery`; for unsettled decisions, explicitly compose `grill-with-docs`; for meaningful executable changes, compose `tdd`; for review, use `code-review`. [Shared skill setup](docs/development.md#shared-skills) names the source and required skills. Report missing prerequisites instead of copying skills into this repository.
- Keep only domain-specific skills with domain code. Reusable methods and OpenSpec integrations belong in `agent-skills`; domain contracts, verification commands, and policy remain here. This bootstrap needs no local skills.
- Planning-only and review-only requests remain read-only. Explicit planning-document requests authorize those documents only. Standalone documentation maintenance follows the delivery default unless the user requests local edits only.
- An implementation/delivery request normally includes issue updates, an isolated worktree, tests, PR publication, independent review, an eligible merge, and final readback. Narrower user instructions prevail. Routine authorized steps do not need repeated confirmation. Installation requires an explicit request.
- This repository deliberately composes the shared TDD and Grill with Docs methods. Their global explicit-only switches stay unchanged. Each substep preserves its own action boundary and returns to the authorized coordinator; it does not discard existing delivery authority.
- Run OpenSpec through `npm run openspec -- <arguments>` from the assigned worktree. Select the exact issue-linked change and local planning root. Use `init --tools none --profile core --no-animation` if initialization is needed; shared integrations are installed from the catalog separately.
- Before synchronization/archive, require complete applicable artifacts and tasks, acceptance evidence, and successful current input lookups. Verify every affected spec. A documented conditional design omission is valid; failed lookups and unfinished work are not. Complete synchronization/archive on the delivery branch before final review.
- The coordinator owns repository and GitHub writes. Obtain independent read-only Standards and Specification reviews against the same committed base/head. Follow [all merge criteria](docs/sdlc.md#review-and-merge), including every configured CI job, the head-commit guard, main CI, and issue readback. Missing independent review or CI prevents automatic merging.
- Preserve other worktrees and their installation owners. Source delivery does not install, alter lights, or clean up another task's branch.

## Runtime boundaries

- Keep light writes in the bridge's single Windows worker. Hooks, the map, and installed WSL entry points coordinate through Windows Python. Linux and Windows SQLite locks on the same mounted file do not exclude each other.
- Keep credentials, databases, live task metadata, scene state, hook files, and installed backups out of Git. The browser must never receive the Nanoleaf token.
- Preserve task pulse epochs, unread tracking, active comet source reservations, saved project preferences, and the user's mode and scene selection during changes.
- Read Codex metadata through the existing reader. Do not write Codex's internal SQLite database or mark tasks read from the map.
- Source changes and tests do not update the installed bridge. For an authorized upgrade, use `bridge/install-modes.ps1`, which backs up state and preserves tasks and trusted hooks. Read `docs/development.md` before installation or physical verification. Do not run fresh `setup` to upgrade an existing installation, because it clears task records.

## Code Review Rules

Flag competing light writers, credentials exposed to the browser or Git, loss of task/scene state, project reservations borrowed by unrelated projects, and animation changes that erase red/yellow alerts or restart completed comets. Review state migrations for backward compatibility and loss of user preferences.

## Human-facing prose

Use the centrally installed `$unslop` skill for the final editorial pass on commentary, responses, and documentation. Preserve facts, commands, contracts, and validation evidence. If it is unavailable, report that and continue without installing or copying it.
