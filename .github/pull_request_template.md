## Change

What behavior changes, and why?

Refs #<issue>. Link the exact OPSX change and ADR when applicable, or explain why
no specification delta is needed. Use Refs so the issue stays open until main CI
and any requested installation checks pass.

## Validation

- [ ] `python3 scripts/check.py` passes.
- [ ] For wall-map changes, `npm run test:browser` passes.
- [ ] For workflow/skill/OPSX changes, `npm run check:workflow` and `npm run test:workflow` pass.
- [ ] Hardware validation is recorded when relevant.

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
- Installation status and owner:
- Physical/controller verification:

Use Not run or Not in scope when evidence is unavailable. A source merge is not
proof of installation or a physical-device update.

## Cross-project work guide, when intentionally updated or published

For a guide revision, link the hub PR and record its snapshot date, source
revisions, changed sections, generated-output hash and checks. For public
publication, record the public PR, deployment, all served URLs and hash
verification. Keep source delivery, guide revision and public publication as
separate claims.

An unrelated change has no guide refresh, companion PR, no-impact entry or
public-currency check. Delete this section when it does not apply.
