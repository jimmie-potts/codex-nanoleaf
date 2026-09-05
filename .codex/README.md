# Codex project setup

Open the repository root as a WSL project in Codex Desktop. `AGENTS.md` supplies project instructions for local tasks and worktrees. There are no Python dependencies to install for the regression suite.

Useful local environment actions:

| Action | Command |
| --- | --- |
| Run tests | `python3 scripts/check.py` |
| Demo wall map | `python3 scripts/demo.py` |
| Browser checks, after development dependency setup | `npm run test:browser` |

Configure these actions in Codex Desktop's local environment settings if you want toolbar buttons. The app generates its environment file under `.codex`; that generated file can be committed. This repository does not override your model, permission, trust, or hook settings.

When Claude Code also works on this repository, follow
[concurrent development and handoffs](../docs/sdlc.md#concurrent-development-and-handoffs).
Keep each writable session in its assigned worktree. Before handing a Codex-managed
worktree to another tool, make its retention explicit in Codex's worktree settings;
do not archive its task while another session owns work there. To avoid that
lifecycle dependency, use an explicitly managed worktree for a cross-tool handoff.

References: [Codex project instructions](https://developers.openai.com/codex/guides/agents-md),
[local environments](https://learn.chatgpt.com/docs/environments/local-environment),
and [Codex worktree lifecycle](https://learn.chatgpt.com/docs/environments/git-worktrees).
