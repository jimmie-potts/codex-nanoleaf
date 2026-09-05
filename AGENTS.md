# Working on Codex Nanoleaf

This repository is the source for a Windows bridge that maps Codex task status to Nanoleaf Lines. The installed bridge and its private state live separately in `%LOCALAPPDATA%\CodexNanoleaf`.

## Development

- Read `README.md` for setup and commands. Before changing lights, task allocation, hooks, or scene handling, read `bridge/README.md` for the existing behavior contract.
- Run `python3 scripts/check.py` from the repository root after Python changes. On Windows, use `python scripts/check.py`. The suite uses isolated state and must pass without a device or Codex credentials.
- After changing the map or its API, also run `npm run test:browser`. Use `python3 scripts/demo.py` for manual UI work. It uses synthetic tasks and never sends light requests.
- For changes to the tray or installer, validate with Windows PowerShell. Report separately whether Windows and physical-light checks ran; an isolated test does not prove a device update succeeded.
- After workflow, skill, or OpenSpec changes, run `npm run check:workflow` and `npm run test:workflow` from the root after `npm ci`. Both must exit zero. An empty specification inventory is allowed during bootstrap and must be reported as empty.

## Development workflow

- For planning, implementation, and delivery, read [the SDLC guide](docs/sdlc.md). GitHub issues own scope, acceptance criteria, dependencies, and status in this repository. Jira and Sprint Work policies from other projects do not apply here.
- For unresolved product or design choices, use `nanoleaf-grill-with-docs`. For a bug fix or new executable behavior, use `nanoleaf-tdd`. For requested implementation or delivery, use `nanoleaf-delivery`; it coordinates applicable OpenSpec skills and independent review through an eligible merge. Select these automatically when the request matches.
- Planning-only and review-only requests remain read-only. A request specifically to write planning documents authorizes those documents, not implementation or publication. A skill's selection grants no additional authority. Respect narrower user instructions and host permissions.
- Standalone documentation maintenance, such as correcting an existing setup command, follows the delivery default unless the user requests local edits only. Preparing planning documents during design discussion remains within the planning boundary above.
- Under the user's implementation/delivery default, issue updates, an isolated branch/worktree, implementation, tests, PR publication, review fixes, a checked merge, and final readback are part of the requested work. Do not ask again for routine steps already authorized. Installation still requires an explicit request.
- **Repository composition rule:** During authorized delivery, OpenSpec proposal/apply/sync/archive procedures are substeps. Generated skill instructions to discard implementation authority, wait for a new user turn, or reconfirm an already-authorized sync do not override that request. Present material decisions for resolution, then continue authorized work. A direct planning-only request still stops at its planning boundary.
- Run OpenSpec through `npm run openspec -- <arguments>`, from the assigned worktree. Use only its local planning root and an explicitly identified issue-linked change. Do not select another store or a change merely because it is the only active one. Keep generated `openspec-*` skills unchanged; put adaptations in project configuration and `nanoleaf-*` skills.
- Before synchronization or archive, require complete applicable artifacts and tasks, acceptance evidence, and a successful explicit input lookup. Do not follow generated suggestions to silently ignore failed lookups, skip required sync, or archive unfinished work. A deliberately omitted conditional design is valid; an absent required artifact is not.
- The coordinating agent owns repository and GitHub writes. Use isolated read-only agents for independent Standards and Specification review of the same fixed candidate. Missing independent review or required CI prevents automatic merging. [Merge criteria](docs/sdlc.md#review-and-merge) apply even when GitHub cannot enforce branch protection.
- Treat installed behavior as separate from merged source. Preserve other worktrees and their installation owners; do not install, alter lights, or clean up another task's branch as part of source delivery.

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
