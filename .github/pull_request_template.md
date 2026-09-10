## Change

What behavior changes, and why?

Refs #<issue>. Link the exact OPSX change and ADR when applicable, or explain why
no specification delta is needed. Use Refs so the issue stays open until main CI
and any requested installation checks pass.

## Validation

- [ ] `python3 scripts/check.py` passes.
- [ ] For wall-map changes, `npm run test:browser` passes.
- [ ] For workflow/skill/OPSX changes, `npm run check:workflow` and `npm run test:workflow` pass.
- [ ] Windows or hardware validation is recorded when relevant.

Record actual commands and results. For TDD, include the check that failed before
the implementation, its failure reason, and the same check passing afterward.
If a red test was impractical, name the limitation and substitute evidence.

## Review and CI

Record the reviewed base, head, merge-base, and diff command. Link independent
Standards and Specification reviews, finding dispositions, and CI for the current
candidate. Recheck unresolved review threads and outstanding change requests.
After merge, append the merged revision and its main CI result.

- UI changes: Yes / No.
- Human approval for this UI candidate: Pending / approval evidence and revision.

UI PRs must remain open until a human approves the current candidate. Agent
reviews and CI do not replace that approval; changed UI needs renewed approval.

## Installation impact

Describe any migration, deployment, or scene/brightness effect. State when the change is source-only.

- Source revision and validation:
- Windows validation:
- Installation status and owner:
- Physical/controller verification:

Use Not run or Not in scope when evidence is unavailable. A source merge is not
proof of installation or a physical-device update.

## Cross-project work guide

- [ ] Linked the coordinated hub guide PR and recorded its synchronization status.
- [ ] Updated affected facts or recorded a specific no-impact reason in the hub maintenance history.
- [ ] Recorded guide validation and any pending post-merge reconciliation.

- Source/tracker completion and revision:
- Guide-source synchronization, Hub companion and revision:
- Public publication PR and revision, or pending/not applicable reason:
- Live deployment, required URLs and served-hash verification:
- Pending stage owner and next action:
