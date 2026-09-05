# Codex project setup

Open the repository root as a WSL project in Codex Desktop. `AGENTS.md` supplies project instructions for local tasks and worktrees. There are no Python dependencies to install for the regression suite.

Useful local environment actions:

| Action | Command |
| --- | --- |
| Run tests | `python3 scripts/check.py` |
| Demo wall map | `python3 scripts/demo.py` |
| Browser checks, after development dependency setup | `npm run test:browser` |

Configure these actions in Codex Desktop's local environment settings if you want toolbar buttons. The app generates its environment file under `.codex`; that generated file can be committed. This repository does not override your model, permission, trust, or hook settings.

References: [Codex project instructions](https://developers.openai.com/codex/guides/agents-md) and [local environments](https://learn.chatgpt.com/docs/environments/local-environment).
