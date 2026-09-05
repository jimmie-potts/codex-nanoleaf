---
name: nanoleaf-grill-with-docs
description: Resolve material product or design choices for Nanoleaf work and prepare documentation proposals. Use for ambiguous planning, requested grilling, or unresolved decisions during an authorized workflow; skip questioning when the choices are already settled.
---

# Nanoleaf decisions and documentation

Read [the SDLC guide](../../../docs/sdlc.md) and applicable agent instructions.
GitHub owns requested scope and dependencies in this repository. This skill
does not select Jira workflows or grant authority to publish or implement.

1. Inspect the relevant code, tests, behavior owners, issue, and decisions through
   authorized read-only tools. Resolve discoverable facts before asking the user.
2. Separate settled choices from unresolved decisions. Map each unresolved
   decision's prerequisites. Ask every independent current decision together;
   keep dependent questions for the next round.
3. For each question, show the decision, meaningful choices, your recommendation,
   and an observable consequence or acceptance boundary. Use the host's input
   tool when available. Wait for answers before dependent work; elapsed time is
   not an answer to a required decision. Continue independent investigation when
   it helps the requested work.
4. Recompute the remaining decisions after each round. Avoid asking the user to
   repeat a settled choice or approve a routine step already authorized.
5. Return accepted decisions, assumptions, unresolved questions, and exact
   proposed documentation paths and changes. Preserve the repository's vocabulary
   and distinguish behavior requirements, issue scope, implementation plans, and
   durable decisions. Use an ADR only for a lasting trade-off.

During questioning, make no repository or GitHub edits. Planning-only and
review-only requests stay read-only. If the underlying request authorizes the
specified document edits, present the concrete proposal and write those documents
after required decisions are settled. That planning-document request alone does not permit
implementation, issue creation, publication, or merge. During an already-authorized
delivery, return the accepted decisions to the coordinating workflow and continue
that work without inventing a new approval requirement.

Standalone maintenance of existing documentation belongs to normal delivery,
unless the user narrows the task to local edits. Do not apply the planning-document
boundary to an ordinary request to correct a setup command or repair a broken link.

Apply the centrally installed `unslop` skill to questions and narrative proposals.
Preserve accepted wording, source quotations, citations, and technical contracts.
