## 1. Skip undeclared sources

- [x] 1.1 Add failing tests for one undeclared session among declared ones, a snapshot of only undeclared sessions, skipped groups and acknowledgment, a declared subagent of an undeclared parent, and declaring a source later; observe `unqualified-source` failures.
- [x] 1.2 Filter undeclared sessions at projection and acknowledgment, report them in inspection, and observe the tests pass.
- [x] 1.3 Add a test that `qualifiedSources` accepts a Claude Code source identity.

## 2. Documentation and delivery

- [x] 2.1 Update `docs/shared-input.md` with the skip behavior, the `skipped` status field and how to declare a source.
- [x] 2.2 Synchronize and archive this change; run the Python and workflow suites.
