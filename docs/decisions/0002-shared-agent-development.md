# ADR 0002: Shared Codex and Claude development

Status: Accepted

Date: 2026-09-05

## Context

[Issue #8](https://github.com/jimmie-potts/codex-nanoleaf/issues/8) adds Claude Code
CLI in WSL alongside Codex Desktop. Both tools must preserve the issue-to-merge
workflow and other active work. They discover instructions and manage worktree
lifetimes differently. Git worktrees isolate working files but share refs and
configuration; the installed Windows bridge remains a separate shared resource.

## Decision

- Keep common repository policy in `AGENTS.md` and the SDLC guide. A short root
  `CLAUDE.md` imports `@AGENTS.md` and points to Claude-specific setup. Use a
  regular import file rather than a Windows-dependent symlink or copied policy.
- Use the same reviewed `agent-skills` catalog for both hosts. Personal setup is
  separately authorized. Record host discovery and source revision rather than
  treating the catalog manager's link status as runtime proof.
- Keep one coordinating writer, issue-based branch, and writable worktree per
  deliverable. Retain the `codex/gh-<issue-number>-<slug>` convention for both
  tools. Explicitly managed Git worktrees are the default for cross-tool work.
- Record ownership and handoffs in GitHub, preserving dirty files and ongoing
  processes. Serialize merges and reread shared state before mutation. These
  procedures do not introduce an atomic lock or background coordinator.
- Keep local sessions, personal settings, and nested worktrees out of Git.
  Neither shared memory nor an old conversation can establish current ownership.
- Preserve all review, CI, human UI approval, and installation boundaries from
  ADR 0001. Claude development support does not add Claude events to the lights.

## Consequences

Common policy can change once for both tools. Host-specific discovery still
needs live validation, and unavailable authentication leaves that evidence
pending. Reusable compatibility changes belong in the catalog's own review.

Worktree ownership depends on agents checking and honoring claims. Concurrent
claims require resolution, and a handoff must account for tool-managed cleanup.
This trades a new coordination service for explicit ownership and current
readback under the existing personal-repository workflow.

The [SDLC guide](../sdlc.md#concurrent-development-and-handoffs) owns the procedure;
[Claude setup](../claude-code.md) owns launch and verification commands. This is
development workflow configuration and documentation with no application
capability delta, so no OpenSpec capability migration is required.
