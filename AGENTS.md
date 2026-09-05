# Working on Codex Nanoleaf

This repository is the source for a Windows bridge that maps Codex task status to Nanoleaf Lines. The installed bridge and its private state live separately in `%LOCALAPPDATA%\CodexNanoleaf`.

## Development

- Read `README.md` for setup and commands. Before changing lights, task allocation, hooks, or scene handling, read `bridge/README.md` for the existing behavior contract.
- Run `python3 scripts/check.py` from the repository root after Python changes. On Windows, use `python scripts/check.py`. The suite uses isolated state and must pass without a device or Codex credentials.
- After changing the map or its API, also run `npm run test:browser`. Use `python3 scripts/demo.py` for manual UI work. It uses synthetic tasks and never sends light requests.
- For changes to the tray or installer, validate with Windows PowerShell. Report separately whether Windows and physical-light checks ran; an isolated test does not prove a device update succeeded.

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
