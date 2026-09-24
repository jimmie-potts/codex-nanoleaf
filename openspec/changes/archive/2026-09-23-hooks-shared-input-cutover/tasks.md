## 1. Hook lifecycle commands

- [x] 1.1 Add temporary-home tests for marked-only removal, byte preservation of unrelated entries, backup creation, idempotent remove/register, and malformed JSON remaining untouched; run them red before implementation and green after.
- [x] 1.2 Implement explicit-home `hooks remove` and `hooks register`, preserving user state and refusing removal in legacy mode; verify both guarded and successful command paths through a generated Linux launcher with a custom state directory.

## 2. Shared-input transition and guidance

- [x] 2.1 Require complete marked hooks before selecting legacy and verify refusal preserves selected source and names `hooks register`.
- [x] 2.2 Document the shared cutover and rollback order in `docs/shared-input.md` and `docs/linux-install.md`; inspect command examples and confirm each rollback registers hooks before selecting legacy.

## 3. Integrated acceptance

- [x] 3.1 Run `python3 scripts/check.py` and confirm all issue #89 temporary-home and transition scenarios pass without a device or personal Codex home.
- [x] 3.2 Synchronize and validate the affected capability spec, run `npm run check:workflow`, and confirm the change is ready for archive.
