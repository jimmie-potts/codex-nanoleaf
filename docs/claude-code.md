# Claude Code setup

Use Claude Code CLI in WSL and Codex Desktop against the WSL source repository.
Both tools follow [AGENTS.md](../AGENTS.md) and the [SDLC guide](sdlc.md).
The root [CLAUDE.md](../CLAUDE.md) imports `@AGENTS.md` so policy has one home.
This setup changes development instructions, not the Nanoleaf status source.

## Prerequisites and skills

Install and authenticate Claude Code separately using
[Anthropic's setup instructions](https://code.claude.com/docs/en/setup).
Check `claude --version` and `claude auth status` in WSL. If authentication is
missing, the user runs `claude auth login`; do not copy credentials into the
repository or another tool's configuration. Python 3.12+, Node.js 22+, Git,
and authenticated GitHub CLI are the existing development prerequisites.

Provision the reviewed catalog using [shared skill setup](development.md#shared-skills)
when personal installation is authorized. Both tools need its delivery,
planning, TDD, OpenSpec, review, and unslop skills. Do not copy shared skills,
generate OpenSpec integrations, or commit external skill symlinks here.

Start a fresh Claude session and use `/context` to confirm the project memory
files. Ask Claude to identify the imported repository rules, canonical test
commands, and read-only versus delivery boundaries. Use `/skills` to inspect
available skills, and verify the source of the catalog's `code-review` skill.
Claude's bundled `/review` alias does not invoke the catalog's `code-review`.
Invoke the shared skill by its full name or load its installed `SKILL.md` when
host discovery is incomplete, reporting that limitation. Do not substitute a
bundled workflow or claim discovery solely from a file existing on disk.

In Codex, start a fresh task in the assigned worktree and check its available
skills and project instructions. Record exact loaded paths and catalog revision
in PR evidence. Missing credentials or skills leave dependent host verification
pending; fixture checks alone cannot establish a working authenticated session.

## Start and resume work

Follow [ownership and handoff rules](sdlc.md#concurrent-development-and-handoffs)
before creating a branch or writing. For an authorized new deliverable, the
coordinator creates an explicitly managed worktree from refreshed `origin/main`.
Run this example from the canonical checkout after substituting the issue,
slug, and a new unoccupied sibling path:

```bash
git worktree list --porcelain
git fetch origin main
git worktree add -b codex/gh-<issue-number>-<slug> ../nanoleaf-gh-<issue-number> origin/main
cd ../nanoleaf-gh-<issue-number>
git status --short --branch
claude
```

The angle-bracket values are placeholders, not literal shell input. Record the
new path, owner, branch, and base in the issue and reread it before edits.
For an existing assigned worktree, inspect its state and launch there; do not
create a second worktree or move an active branch to another checkout.

Resume with `claude --resume <session-id>` from that worktree after confirming
ownership. Resuming a conversation does not reclaim ownership from a newer
writer. For a cross-tool handoff, stop the outgoing writer and retain the same
worktree until the incoming writer has accepted its recorded state. Open that
path as a local Codex project/task when transferring to Codex; do not launch an
additional writable session from the original checkout.

Claude's native `claude --worktree <name>` can create its own branch and uses
`.claude/worktrees/` by default. The explicit Git procedure above keeps this
repo's branch names and ownership predictable. Do not call it inside an already
assigned worktree or reuse another owner's native worktree name. Claude may
offer cleanup at session exit; retain the worktree while changes, commits, a
handoff, or another session still depend on it. Codex-managed worktrees have a
separate retention lifecycle; see [Codex setup](../.codex/README.md).

## Validate and preserve local state

Run checks from the assigned worktree. Use the commands in
[development and deployment](development.md#validate-a-change), including
`npm ci`, `npm run check:workflow`, and `npm run test:workflow` for workflow edits.
Each concurrent demo needs its own port and temporary synthetic state. No
development check authorizes installation or a request to physical lights.

Keep personal `CLAUDE.local.md`, `.claude/settings.local.json`, and generated
worktree/session artifacts ignored. Tracked instructions and any future reviewed
project settings remain visible to Git. Do not change personal permission,
trust, model, hook, MCP, or auto-memory settings as part of source delivery.
Claude auto memory may be shared across worktrees, so use issue/PR records for
ownership and handoff. Never copy private state into worktrees to make a test
pass or add it to `.worktreeinclude`.

For acceptance exercises, use a disposable repository and separate Codex and
Claude worktrees. Check instruction/skill loading in fresh sessions at its root
and worktree. Give each writer a different synthetic edit and test, then compare
the other worktree's HEAD, branch, and contents. Exercise a dirty handoff and
refusal to remove it, plus planning-only, review-only, and ineligible-merge
scenarios. Record observed actions, tool versions, catalog revision, and failed
or unavailable checks in the PR. Keep fixture artifacts outside product Git.

## References

- [Claude project instructions and imports](https://code.claude.com/docs/en/memory#agentsmd)
- [Claude skills and name resolution](https://code.claude.com/docs/en/skills)
- [Claude worktrees and cleanup](https://code.claude.com/docs/en/worktrees)
- [Claude verification and planning practices](https://code.claude.com/docs/en/best-practices)
- [Codex project instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Codex worktree lifecycle](https://learn.chatgpt.com/docs/environments/git-worktrees)
